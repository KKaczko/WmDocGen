"""Stage 4 of the conditional-flow work: decision-aware prompts and checked detailed flows."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from flowxml import FlowPackage, branch, case, copy, exit_, invoke, loop, record, string

from wm_doc.config import load_config
from wm_doc.describer import (
    DescribeOptions,
    DescribeOutcome,
    DetailLevel,
    approve_docs,
    collect_states,
    current_facts_hashes,
    describe_services,
    upgrade_blocker,
)
from wm_doc.flow_answers import FlowItem, FlowRule, check_items
from wm_doc.flow_logic import compute_flow_logic
from wm_doc.flow_semantics import RULES_BY_ID, RuleStatus
from wm_doc.ir import AnalysisResult
from wm_doc.ollama_provider import (
    ProviderCheckResult,
    ProviderGenerationRequest,
    ProviderGenerationResult,
)
from wm_doc.service_docs import (
    BASIS_KEY,
    UNVERIFIED_FLOW_KEY,
    DocState,
    DocStatus,
    Narrative,
    doc_path,
    new_doc,
    read_doc,
    write_doc,
)

SUBJECT = "orders.api:processOrder"
Items = list[dict[str, Any]]
Answer = Callable[[int, ProviderGenerationRequest], Items]


class FlowProvider:
    """Answers every request with the same narrative and the detailed items `answer` gives."""

    def __init__(self, answer: Answer) -> None:
        self.answer = answer
        self.requests: list[ProviderGenerationRequest] = []

    def check(self, model: str) -> ProviderCheckResult:
        return ProviderCheckResult(
            provider_kind="ollama",
            model=model,
            ollama_version="test",
            model_digest="sha256:test",
            model_found=True,
        )

    def generate(self, request: ProviderGenerationRequest) -> ProviderGenerationResult:
        self.requests.append(request)
        payload = {
            "purpose": "Processes an order according to its status.",
            "usage": "Used by the callers listed in the facts.",
            "data_effects": "Reads the request status.",
            "steps": ["Checks the status.", "Calls the services for it."],
            "detailed_steps": self.answer(len(self.requests), request),
            "error_handling": "Not shown in the facts.",
            "designer_comment": "Processes an order.",
        }
        return ProviderGenerationResult(
            content=json.dumps(payload),
            provider_kind="ollama",
            model=request.model,
            ollama_version="test",
            model_digest="sha256:test",
            metrics={"prompt_eval_count": 400},
        )

    def prompt(self, index: int = 0) -> str:
        return self.requests[index].messages[1]["content"]

    def last_user_message(self, index: int) -> str:
        return self.requests[index].messages[-1]["content"]


def _item(
    text: str, decision: str = "", case_id: str = "", calls: tuple[str, ...] = ()
) -> dict[str, Any]:
    return {"text": text, "decision": decision, "case": case_id, "calls": list(calls)}


GOOD: Items = [
    _item(
        "Calls `systemA:validateOrder` and copies `/result/status` to `/validationStatus`.",
        "D1",
        "D1.c1",
        ("C1",),
    ),
    _item("Calls `systemB:finalizeOrder`.", "D1", "D1.c2", ("C2",)),
    _item("Calls `systemC:activateOrder`.", "D2", "D2.c1", ("C3",)),
    _item("Calls `common:handleError`.", "D2", "D2.c2", ("C4",)),
]
ONE_ITEM: Items = [
    _item("Validates, finalizes, activates or handles errors.", calls=("C1", "C2", "C3", "C4"))
]
STOP = branch(case("STOP", exit_("$flow")), switch="/stop")


def _with(items: Items, index: int, **changes: Any) -> Items:
    changed = [dict(item) for item in items]
    changed[index].update(changes)
    return changed


def _package(root: Path, *extra: str) -> FlowPackage:
    pkg = FlowPackage(root, "Orders")
    pkg.service(
        SUBJECT,
        branch(
            case(
                "ACTIVE",
                invoke(
                    "systemA:validateOrder", outputs=[copy("/result/status", "/validationStatus")]
                ),
            ),
            case("FINALIZED", invoke("systemB:finalizeOrder")),
            switch="/request/status",
        ),
        branch(
            case("OK", invoke("systemC:activateOrder")),
            case("ERROR", invoke("common:handleError")),
            switch="/validationStatus",
        ),
        *extra,
        inputs=[record("request", [string("status")])],
    )
    return pkg


class Setup:
    def __init__(self, tmp_path: Path, *extra: str) -> None:
        self.root = tmp_path / "packages"
        self.analysis: AnalysisResult = _package(self.root, *extra).analyze()
        self.docs = tmp_path / "service-docs"
        self.cache = tmp_path / "cache"

    def options(self, **overrides: Any) -> DescribeOptions:
        values: dict[str, Any] = {
            "model": "fake-model",
            "scan_root": self.root,
            "config": load_config(None),
            "docs_dir": self.docs,
            "cache_dir": self.cache,
        }
        values.update(overrides)
        return DescribeOptions(**values)

    def describe(self, answer: Answer, **overrides: Any) -> tuple[FlowProvider, DescribeOutcome]:
        provider = FlowProvider(answer)
        results, _stats = describe_services(
            self.analysis, [SUBJECT], provider, self.options(**overrides)
        )
        return provider, results[0].outcome

    def path(self) -> Path:
        return doc_path(self.docs, "Orders", SUBJECT)

    def text(self) -> str:
        return self.path().read_text(encoding="utf-8")

    def hash(self, basis: int) -> str:
        return current_facts_hashes(
            self.analysis, self.root, load_config(None), bases={SUBJECT: basis}
        )[SUBJECT]


def _always(items: Items) -> Answer:
    return lambda _index, _request: items


def _first_then(first: Items, later: Items) -> Answer:
    return lambda index, _request: first if index == 1 else later


# --- the prompt -----------------------------------------------------------------------------


def test_the_prompt_carries_decision_case_and_call_ids(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    provider, _outcome = setup.describe(_always(GOOD))

    prompt = provider.prompt()
    assert "[D1] BRANCH on /request/status:" in prompt
    assert '[D1.c1] when "ACTIVE":' in prompt
    assert "[C1] CALL systemA:validateOrder" in prompt
    assert "decisions (ids for detailed_steps" in prompt
    assert "D1.c1 `/request/status` is `ACTIVE`: C1" in prompt
    schema = provider.requests[0].schema["properties"]["detailed_steps"]
    assert schema["items"]["required"] == ["text", "decision", "case", "calls"]


# --- checked detailed flows ------------------------------------------------------------------


def test_a_correct_answer_passes_and_the_tool_writes_the_conditions(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    provider, outcome = setup.describe(_always(GOOD))

    assert outcome is DescribeOutcome.GENERATED
    assert len(provider.requests) == 1
    text = setup.text()
    narrative = text.split("## Notes")[0]
    assert (
        "1. When `/request/status` is `ACTIVE` (D1): Calls `systemA:validateOrder` and copies"
    ) in narrative
    assert "3. When `/validationStatus` is `OK` (D2): Calls `systemC:activateOrder`." in narrative
    assert '"calls"' not in narrative and "D1.c1" not in narrative
    assert f"{BASIS_KEY}: 2\n" in text


def test_everything_in_one_item_fails_and_is_corrected(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    provider, outcome = setup.describe(_first_then(ONE_ITEM, GOOD))

    assert outcome is DescribeOutcome.GENERATED
    assert len(provider.requests) == 2
    correction = provider.last_user_message(1)
    assert "C1" in correction and "D1.c1" in correction


def test_everything_in_one_item_is_rejected_when_it_stays_wrong(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    provider, outcome = setup.describe(_always(ONE_ITEM))

    assert outcome is DescribeOutcome.REJECTED
    assert len(provider.requests) == 2
    assert not setup.path().exists()


def test_a_call_under_the_wrong_case_fails(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    wrong = _with(GOOD, 2, decision="D1", case="D1.c1")

    _provider, outcome = setup.describe(_always(wrong))

    assert outcome is DescribeOutcome.REJECTED


def test_unknown_ids_fail(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    _provider, outcome = setup.describe(_always([*GOOD, _item("Ends.", calls=("C9",))]))

    assert outcome is DescribeOutcome.REJECTED


def test_a_left_out_call_fails(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    _provider, outcome = setup.describe(_always(GOOD[:3]))

    assert outcome is DescribeOutcome.REJECTED


def test_an_invented_value_fails_thorough_but_is_only_counted_in_standard(
    tmp_path: Path,
) -> None:
    invented = _with(GOOD, 3, text='When the status is "PENDING", calls `common:handleError`.')

    standard = Setup(tmp_path / "standard")
    _provider, outcome = standard.describe(_always(invented))
    assert outcome is DescribeOutcome.GENERATED

    thorough = Setup(tmp_path / "thorough")
    _provider, outcome = thorough.describe(_always(invented), detail=DetailLevel.THOROUGH)
    assert outcome is DescribeOutcome.REJECTED


def test_always_for_a_guarded_call_fails_thorough(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    always = _with(GOOD, 2, text="Always activates the order with `systemC:activateOrder`.")

    _provider, outcome = setup.describe(_always(always), detail=DetailLevel.THOROUGH)

    assert outcome is DescribeOutcome.REJECTED


def test_naming_a_call_the_item_does_not_list_fails_thorough(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    named = _with(GOOD, 0, text="Calls `systemA:validateOrder`, then `systemC:activateOrder`.")

    _provider, outcome = setup.describe(_always(named), detail=DetailLevel.THOROUGH)

    assert outcome is DescribeOutcome.REJECTED


def test_a_decision_without_an_item_fails_thorough(tmp_path: Path) -> None:
    missing = Setup(tmp_path / "missing", STOP)
    _provider, outcome = missing.describe(_always(GOOD), detail=DetailLevel.THOROUGH)
    assert outcome is DescribeOutcome.REJECTED

    covered = [*GOOD, _item("Stops the service.", "D3", "D3.c1")]
    _provider, outcome = Setup(tmp_path / "covered", STOP).describe(
        _always(covered), detail=DetailLevel.THOROUGH
    )
    assert outcome is DescribeOutcome.GENERATED


def test_thorough_gets_one_more_request_for_flow_problems(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    answers = [ONE_ITEM, ONE_ITEM, GOOD]

    provider, outcome = setup.describe(
        lambda index, _request: answers[min(index, 3) - 1], detail=DetailLevel.THOROUGH
    )

    assert outcome is DescribeOutcome.GENERATED
    assert len(provider.requests) == 3


def test_keep_unverified_keeps_a_flow_that_stays_wrong_marked(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    _provider, outcome = setup.describe(_always(ONE_ITEM), keep_unverified=True)

    assert outcome is DescribeOutcome.UNVERIFIED
    doc = read_doc(setup.path())
    assert doc is not None
    assert doc.extra_front_matter.get(UNVERIFIED_FLOW_KEY)
    assert "**Unverified flow:**" in setup.text()
    # It is asked again on the next run, and approving it clears the mark.
    provider, outcome = setup.describe(_always(GOOD))
    assert outcome is DescribeOutcome.GENERATED and len(provider.requests) == 1
    setup.describe(_always(ONE_ITEM), keep_unverified=True, redo_drafts=True, no_cache=True)
    approve_docs(setup.docs, services=[SUBJECT])
    doc = read_doc(setup.path())
    assert doc is not None and UNVERIFIED_FLOW_KEY not in doc.extra_front_matter


def test_ids_written_with_brackets_or_in_lower_case_are_read(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    loose = [
        _with(GOOD, 0, decision="[D1]", case="d1.C1", calls=["[c1]"])[0],
        _with(GOOD, 1, calls=["C2."])[1],
        *GOOD[2:],
    ]

    provider, outcome = setup.describe(_always(loose))

    assert outcome is DescribeOutcome.GENERATED
    assert len(provider.requests) == 1


def test_text_that_is_not_an_id_is_never_repeated(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    odd = _with(GOOD, 1, case="sk-live-abcdefghijkl", calls=["see https://example.invalid"])

    provider, outcome = setup.describe(_always(odd), keep_unverified=True)

    assert outcome is DescribeOutcome.UNVERIFIED
    correction = provider.last_user_message(1)
    assert "an id that is not in the facts" in correction
    for text in (correction, setup.text()):
        assert "sk-live" not in text and "example.invalid" not in text


def test_unknown_names_and_flow_problems_are_corrected_together(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    first = _with(GOOD[:3], 0, text="Calls `systemZ:invented` first.")

    provider, outcome = setup.describe(_first_then(first, GOOD))

    assert outcome is DescribeOutcome.GENERATED
    correction = provider.last_user_message(1)
    assert "do not appear in the facts" in correction
    assert "no item lists call C4" in correction


def test_naming_a_later_call_that_runs_in_no_case_is_fine(tmp_path: Path) -> None:
    setup = Setup(tmp_path, invoke("orders.audit:record"))
    named = [
        *_with(GOOD, 0, text="Calls `systemA:validateOrder`; `orders.audit:record` runs later."),
        _item("Records the order with `orders.audit:record`.", calls=("C5",)),
    ]

    _provider, outcome = setup.describe(_always(named), detail=DetailLevel.THOROUGH)

    assert outcome is DescribeOutcome.GENERATED


def test_always_is_fine_for_a_call_that_runs_on_every_iteration(tmp_path: Path) -> None:
    setup = Setup(tmp_path, loop(invoke("orders.audit:record"), in_array="/request/lines"))
    items = [*GOOD, _item("For each line, always calls `orders.audit:record`.", calls=("C5",))]

    _provider, outcome = setup.describe(_always(items), detail=DetailLevel.THOROUGH)

    assert outcome is DescribeOutcome.GENERATED


def test_calls_and_decisions_cut_from_the_prompt_are_not_required(tmp_path: Path) -> None:
    logic = compute_flow_logic(Setup(tmp_path).analysis.services[0])
    items = [FlowItem("Calls it.", "D1", "D1.c1", ("C1",))]

    assert check_items(items, logic, ("C1", "C2"), "[D1] [D1.c1] [C1]") == []
    found = check_items(items, logic, ("C1", "C2"), "[D1] [D1.c1] [C1] [D2] [C2]")
    assert {item.rule for item in found} == {FlowRule.R3, FlowRule.R4}


def test_brief_descriptions_have_no_flow_and_no_flow_checks(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    provider, outcome = setup.describe(_always(ONE_ITEM), detail=DetailLevel.BRIEF)

    assert outcome is DescribeOutcome.GENERATED
    assert "detailed_steps" not in provider.requests[0].schema["properties"]
    assert "## Detailed flow" not in setup.text()


# --- the facts hash --------------------------------------------------------------------------


def test_old_approved_descriptions_stay_approved_until_upgraded(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    legacy = setup.hash(1)
    # A description approved before stage 4: legacy facts hash, no facts_basis key.
    setup.describe(_always(GOOD))
    doc = read_doc(setup.path())
    assert doc is not None
    doc.extra_front_matter.pop(BASIS_KEY)
    doc.facts_hash = legacy
    doc.current_facts_hash = legacy
    doc.status = DocStatus.APPROVED
    write_doc(setup.path(), doc)

    provider, outcome = setup.describe(_always(GOOD))

    assert outcome is DescribeOutcome.PROTECTED and not provider.requests
    hashes = current_facts_hashes(
        setup.analysis, setup.root, load_config(None), bases={SUBJECT: 1}
    )
    assert collect_states(setup.analysis, setup.docs, hashes)[SUBJECT][1] is DocState.APPROVED
    assert f"next={setup.hash(2)}" in setup.text()

    approved, missing = approve_docs(setup.docs, services=[SUBJECT], upgrade_basis=True)

    assert approved == [SUBJECT] and missing == []
    doc = read_doc(setup.path())
    assert doc is not None
    assert doc.extra_front_matter[BASIS_KEY] == 2
    assert doc.facts_hash == setup.hash(2)
    hashes = current_facts_hashes(
        setup.analysis, setup.root, load_config(None), bases={SUBJECT: 2}
    )
    assert collect_states(setup.analysis, setup.docs, hashes)[SUBJECT][1] is DocState.APPROVED


def test_an_approved_description_whose_facts_changed_is_not_upgraded(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    setup.describe(_always(GOOD))
    doc = read_doc(setup.path())
    assert doc is not None
    doc.extra_front_matter.pop(BASIS_KEY)
    doc.facts_hash = "0" * 16  # approved against facts that have changed since
    doc.status = DocStatus.APPROVED
    write_doc(setup.path(), doc)
    setup.describe(_always(GOOD))  # refreshes the marker: current hash and next=
    doc = read_doc(setup.path())
    assert doc is not None and doc.next_facts_hash == setup.hash(2)
    assert upgrade_blocker(doc) == (
        "its facts changed after it was approved; set status: draft and review it first"
    )

    approved, _missing = approve_docs(setup.docs, services=[SUBJECT], upgrade_basis=True)

    assert approved == []
    doc = read_doc(setup.path())
    assert doc is not None
    assert doc.facts_hash == "0" * 16 and doc.facts_basis == 1


def test_basis_two_hashes_the_control_logic(tmp_path: Path) -> None:
    first = Setup(tmp_path / "first")
    second = Setup(tmp_path / "second", branch(case("X", invoke("x.api:x")), switch="/x"))

    assert first.hash(1) != first.hash(2)
    assert first.hash(2) != second.hash(2)


def test_a_rule_status_never_changes_the_basis_two_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    setup = Setup(tmp_path)
    before = setup.hash(2)
    for rule_id in RULES_BY_ID:
        flipped = RuleStatus.DOCUMENTED if RULES_BY_ID[rule_id].assumed else RuleStatus.ASSUMED
        monkeypatch.setitem(RULES_BY_ID, rule_id, replace(RULES_BY_ID[rule_id], status=flipped))

    assert setup.hash(2) == before


def test_new_drafts_record_basis_two(tmp_path: Path) -> None:
    setup = Setup(tmp_path)

    setup.describe(_always(GOOD))

    doc = read_doc(setup.path())
    assert doc is not None
    assert doc.facts_hash == setup.hash(2)
    assert re.search(r"<!-- wm-doc:facts:start hash=[0-9a-f]+ -->", setup.text())


def test_an_old_unedited_draft_with_unchanged_facts_is_kept(tmp_path: Path) -> None:
    setup = Setup(tmp_path)
    legacy = setup.hash(1)
    old = new_doc(
        SUBJECT,
        "Orders",
        Narrative("Old.", "Old.", "Old.", ("Old.",), "Old.", "Old."),
        model="old-model",
        facts="legacy",
        facts_markdown="",
    )
    old.facts_hash = legacy
    old.current_facts_hash = legacy
    write_doc(setup.path(), old)

    provider, outcome = setup.describe(_always(GOOD))

    # An unedited basis-1 draft whose legacy facts are unchanged is kept as it is.
    assert outcome is DescribeOutcome.UNCHANGED and not provider.requests
