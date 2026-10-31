"""Stage 3 of the conditional-flow work: scenarios along data-dependency chains."""

from __future__ import annotations

import re
import time
from dataclasses import replace
from pathlib import Path

import pytest
from flowxml import (
    Field,
    FlowPackage,
    branch,
    case,
    copy,
    exit_,
    invoke,
    loop,
    map_,
    record,
    seq,
    set_,
    string,
    try_catch,
)

from wm_doc.config import ExtractionMode
from wm_doc.flow_lineage import compute_flow_lineage
from wm_doc.flow_logic import compute_flow_logic
from wm_doc.flow_scenarios import (
    MAX_CHAIN,
    MAX_SCENARIOS,
    Feasibility,
    FlowScenarios,
    OutcomeKind,
    Scenario,
    ScenarioTable,
    compute_flow_scenarios,
)
from wm_doc.flow_semantics import RULES_BY_ID, RuleStatus
from wm_doc.ir import AnalysisResult
from wm_doc.render.flow_markdown import render_decisions_section

SUBJECT = "scenario.api:subject"


class Subject:
    def __init__(self, analysis: AnalysisResult) -> None:
        self.service = next(
            item for item in analysis.services if item.identity.full_name == SUBJECT
        )
        signatures = {item.identity.full_name: item.signature for item in analysis.services}
        logic = compute_flow_logic(self.service)
        assert logic is not None
        self.logic = logic
        self.lineage = compute_flow_lineage(self.service, logic, signatures)
        scenarios = compute_flow_scenarios(self.service, logic, self.lineage, signatures)
        assert scenarios is not None
        self.scenarios: FlowScenarios = scenarios

    def table(self, *decisions: str) -> ScenarioTable:
        return next(item for item in self.scenarios.tables if item.decision_ids == decisions)

    def text(self) -> str:
        return render_decisions_section(self.logic, self.lineage, self.scenarios)

    def section(self) -> str:
        text = self.text()
        return text.split("### Scenarios", 1)[1].split("### Calls by condition", 1)[0]


def _subject(
    tmp_path: Path,
    *steps: str,
    literals: ExtractionMode | None = None,
    inputs: list[Field] | None = None,
) -> Subject:
    pkg = FlowPackage(tmp_path / "packages", "Scenario")
    pkg.service(SUBJECT, *steps, inputs=inputs)
    return Subject(pkg.analyze(literals=literals))


def _conditions(scenario: Scenario) -> list[tuple[str, OutcomeKind, tuple[str, ...], bool]]:
    return [
        (item.decision_id, item.kind, item.case_ids, item.no_match) for item in scenario.outcomes
    ]


def _process_order(tmp_path: Path) -> Subject:
    return _subject(
        tmp_path,
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
        inputs=[record("request", [string("status")])],
    )


def _chain(length: int, labels: tuple[str, ...] = ("X",)) -> list[str]:
    """D1 tests /v0 and sets /v1 in its cases, D2 tests /v1 and sets /v2, and so on."""
    return [
        branch(
            *(
                case(label, map_(set_(f"/v{index + 1}", f"{label}{index}")))
                for label in labels
            ),
            switch=f"/v{index}",
        )
        for index in range(length)
    ]


# --- F1: processOrder -----------------------------------------------------------------------


def test_process_order_combines_its_two_decisions(tmp_path: Path) -> None:
    subject = _process_order(tmp_path)

    table = subject.table("D1", "D2")
    assert subject.scenarios.dependencies == (("D1", "D2"),)
    first = [scenario.outcomes[0] for scenario in table.scenarios]
    # ACTIVE leads to other origins of /validationStatus than FINALIZED or no match, which
    # share them (only the caller's pipeline), so those two are grouped (three groups in all).
    groups = list(dict.fromkeys((item.kind, item.case_ids, item.no_match) for item in first))
    assert groups == [
        (OutcomeKind.CASE, ("D1.c1",), False),
        (OutcomeKind.CASE, ("D1.c2",), True),
        (OutcomeKind.FAILS, (), False),
    ]
    active = [item for item in table.scenarios if item.outcomes[0].case_ids == ("D1.c1",)]
    assert [_conditions(item)[1][1:] for item in active] == [
        (OutcomeKind.CASE, ("D2.c1",), False),
        (OutcomeKind.CASE, ("D2.c2",), False),
        (OutcomeKind.NO_MATCH, (), True),
        (OutcomeKind.FAILS, (), False),
    ]
    assert active[0].call_ids == ("C1", "C3")
    assert active[0].depends_on_calls == ("C1",)
    assert all(item.feasibility is Feasibility.CONDITIONAL for item in table.scenarios)
    assert len(table.scenarios) == 9
    assert not table.truncated
    failed = table.scenarios[-1]
    assert _conditions(failed) == [
        ("D1", OutcomeKind.FAILS, (), False),
        ("D2", OutcomeKind.NOT_REACHED, (), False),
    ]

    section = subject.section()
    assert "D1 = `FINALIZED` or no case matches; D2 = `OK`" in section
    assert "C2 `systemB:finalizeOrder` (only when D1 = `FINALIZED`)" in section
    assert "D1 fails: `/request/status` is missing (S31)" in section
    assert "the service fails" in section


def test_the_scenarios_section_sits_inside_decisions(tmp_path: Path) -> None:
    text = _process_order(tmp_path).text()

    assert text.index("### D2:") < text.index("### Scenarios") < text.index("### Calls by")


# --- independent decisions --------------------------------------------------------------------


def test_independent_branches_are_never_multiplied(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        *(
            branch(case("A", invoke(f"x.api:call{index}")), switch=f"/s{index}")
            for index in range(10)
        ),
    )

    assert subject.scenarios.tables == ()
    assert subject.scenarios.independent == tuple(f"D{index}" for index in range(1, 11))
    assert "### Scenarios" not in subject.text()


def test_a_shared_root_gives_one_table_per_chain(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(case("A", map_(set_("/x", "1"), set_("/y", "2"))), switch="/s"),
        branch(case("1", invoke("x.api:x")), switch="/x"),
        branch(case("2", invoke("x.api:y")), switch="/y"),
    )

    assert [table.decision_ids for table in subject.scenarios.tables] == [
        ("D1", "D2"),
        ("D1", "D3"),
    ]


def test_decisions_inside_loops_are_not_combined(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        loop(
            branch(case("A", map_(set_("/t", "B"))), switch="/items/kind"),
            branch(case("B", invoke("x.api:b")), switch="/t"),
            in_array="/items",
        ),
    )

    assert subject.scenarios.tables == ()
    assert subject.scenarios.in_loops == ("D1", "D2")


# --- pruning ------------------------------------------------------------------------------


def test_a_unique_literal_rules_out_other_values(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(case("K", map_(set_("/t", "AB"))), switch="/k"),
        branch(case("AB", invoke("x.api:ab")), case("X", invoke("x.api:x")), switch="/t"),
    )

    table = subject.table("D1", "D2")
    after_k = [item for item in table.scenarios if item.outcomes[0].case_ids == ("D1.c1",)]
    # Parsed labels are trimmed, so an equal label never rules out "no case matches".
    assert [_conditions(item)[1][1:] for item in after_k] == [
        (OutcomeKind.CASE, ("D2.c1",), False),
        (OutcomeKind.NO_MATCH, (), True),
    ]
    # /k still comes from the caller.
    assert after_k[0].feasibility is Feasibility.CONDITIONAL
    ruled = [(item.decision_id, item.case_id, item.value) for item in table.ruled_out]
    assert ruled == [("D2", "D2.c2", "AB")]
    assert "Ruled out" in subject.section()


def test_a_literal_with_surrounding_blanks_rules_nothing_out(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(case("K", map_(set_("/t", "AB "))), switch="/k"),
        branch(case("AB", invoke("x.api:ab")), case("X", invoke("x.api:x")), switch="/t"),
    )

    assert subject.table("D1", "D2").ruled_out == ()


def test_values_this_service_sets_make_a_scenario_possible(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/k", "K")),
        branch(case("K", map_(set_("/t", "AB"))), switch="/k"),
        branch(case("AB", invoke("x.api:ab")), case("X", invoke("x.api:x")), switch="/t"),
    )

    scenario = subject.table("D1", "D2").scenarios[0]
    assert _conditions(scenario) == [
        ("D1", OutcomeKind.CASE, ("D1.c1",), False),
        ("D2", OutcomeKind.CASE, ("D2.c1",), False),
    ]
    assert scenario.feasibility is Feasibility.POSSIBLE


@pytest.mark.parametrize("variant", ["pattern", "redacted", "expression"])
def test_patterns_expressions_and_redacted_values_are_never_ruled_out(
    tmp_path: Path, variant: str
) -> None:
    second = {
        "pattern": branch(
            case("/^X/", invoke("x.api:p")), case("X", invoke("x.api:x")), switch="/t"
        ),
        "redacted": branch(case("X", invoke("x.api:x")), switch="/t"),
        "expression": branch(case("%t% == 'X'", invoke("x.api:x")), expressions=True),
    }[variant]
    subject = _subject(
        tmp_path,
        branch(case("K", map_(set_("/t", "AB"))), switch="/k"),
        second,
        literals=ExtractionMode.REDACT if variant == "redacted" else None,
    )

    table = subject.table("D1", "D2")
    pruned_cases = {item.case_id for item in table.ruled_out if item.decision_id == "D2"}
    if variant == "pattern":
        assert "D2.c1" not in pruned_cases  # the pattern case stays
        assert None not in pruned_cases  # no case matches stays: the pattern may not match
    else:
        assert table.ruled_out == ()
    after_k = [item for item in table.scenarios if item.outcomes[0].case_ids == ("D1.c1",)]
    assert any(item.outcomes[1].kind is OutcomeKind.CASE for item in after_k)


# --- limits -------------------------------------------------------------------------------


def test_the_scenario_cap_marks_truncation(tmp_path: Path) -> None:
    labels = ("/^a/", "/^b/", "/^c/")
    subject = _subject(tmp_path, *_chain(4, labels))

    table = subject.table("D1", "D2", "D3", "D4")
    assert table.truncated
    assert len(table.scenarios) == MAX_SCENARIOS
    assert f"at most {MAX_SCENARIOS} scenarios are listed" in subject.section()


def test_chains_longer_than_four_decisions_are_cut(tmp_path: Path) -> None:
    subject = _subject(tmp_path, *_chain(6))

    (table,) = subject.scenarios.tables
    assert table.decision_ids == tuple(f"D{index}" for index in range(1, MAX_CHAIN + 1))
    assert table.left_out == ("D5", "D6")
    assert "D5, D6 also depend on these decisions and are not combined" in subject.section()


# --- reach -----------------------------------------------------------------------------------


def test_a_decision_some_paths_skip_may_be_not_reached(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(case("A", map_(set_("/t", "B"))), case("C", map_(set_("/t", "Q"))), switch="/k"),
        branch(case("Z", exit_("$flow")), switch="/z"),
        branch(case("B", invoke("x.api:b")), case("Q", invoke("x.api:q")), switch="/t"),
    )

    table = subject.table("D1", "D3")
    after_a = [item for item in table.scenarios if item.outcomes[0].case_ids == ("D1.c1",)]
    assert OutcomeKind.NOT_REACHED in [item.outcomes[1].kind for item in after_a]
    assert OutcomeKind.CASE in [item.outcomes[1].kind for item in after_a]


def test_a_catch_decision_may_be_not_reached_when_the_try_succeeds(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        try_catch(
            [branch(case("A", map_(set_("/t", "B"))), switch="/k")],
            [branch(case("B", invoke("x.api:b")), switch="/t")],
        ),
    )

    table = subject.table("D1", "D2")
    after_a = [item for item in table.scenarios if item.outcomes[0].case_ids == ("D1.c1",)]
    assert OutcomeKind.NOT_REACHED in [item.outcomes[1].kind for item in after_a]
    # With no case matching, the BRANCH does nothing, so the TRY cannot fail and D2 never runs.
    no_match = [item for item in table.scenarios if item.outcomes[0].kind is OutcomeKind.NO_MATCH]
    assert [item.outcomes[1].kind for item in no_match] == [OutcomeKind.NOT_REACHED]


def test_steps_after_an_exit_are_never_scenario_calls(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(
            case("A", map_(set_("/t", "B"))),
            case(
                "C",
                exit_("$parent", "FAILURE"),
                seq(invoke("x.api:work"), name="Try", form="TRY"),
                seq(invoke("x.api:neverRuns"), name="Catch", form="CATCH"),
            ),
            switch="/k",
        ),
        branch(case("B", invoke("x.api:b")), switch="/t"),
    )

    table = subject.table("D1", "D2")
    never = next(call for call in subject.logic.calls if call.target == "x.api:neverRuns")
    assert all(never.id not in item.call_ids for item in table.scenarios)
    after_c = [item for item in table.scenarios if item.outcomes[0].case_ids == ("D1.c2",)]
    assert [item.outcomes[1].kind for item in after_c] == [OutcomeKind.NOT_REACHED]


def test_a_call_that_needs_another_decision_says_so(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(
            case(
                "A",
                map_(set_("/t", "B")),
                branch(case("Q", invoke("x.api:onlyWhenQ")), switch="/q"),
            ),
            switch="/k",
        ),
        branch(case("B", invoke("x.api:b")), switch="/t"),
    )

    assert "C1 `x.api:onlyWhenQ` (also only when D2 = `Q`)" in subject.section()


def test_a_call_in_between_may_drop_the_field(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(case("A", map_(set_("/t", "B"))), case("C", map_(set_("/t", "X"))), switch="/k"),
        invoke("x.api:mayDropT"),
        branch(case("B", invoke("x.api:b")), case("X", invoke("x.api:x")), switch="/t"),
    )

    table = subject.table("D1", "D2")
    after_a = [item for item in table.scenarios if item.outcomes[0].case_ids == ("D1.c1",)]
    assert OutcomeKind.FAILS in [item.outcomes[1].kind for item in after_a]


def test_a_catch_decision_carries_the_try_catch_assumption(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        try_catch(
            [branch(case("A", map_(set_("/t", "B"))), switch="/k")],
            [branch(case("B", invoke("x.api:b")), switch="/t")],
        ),
    )

    reached = [
        item
        for item in subject.table("D1", "D2").scenarios
        if item.outcomes[1].kind is OutcomeKind.CASE
    ]
    assert reached
    assert all("S14" in item.rules for item in reached)


def test_the_walk_limit_never_leaves_an_empty_table(tmp_path: Path) -> None:
    labels = ("/^a/", "/^b/", "/^c/", "/^d/")
    root = branch(
        *(
            case(label, map_(*(set_(f"/t{index}", label) for index in range(10))))
            for label in labels
        ),
        switch="/k",
    )
    later = [
        branch(*(case(label, invoke(f"x.api:c{index}")) for label in labels), switch=f"/t{index}")
        for index in range(10)
    ]
    subject = _subject(tmp_path, root, *later)

    section = subject.section()
    for table in subject.scenarios.tables:
        if not table.scenarios:
            assert f"{', '.join(table.decision_ids)} depend on each other" in section
        elif table.walk_limit:
            assert "the limit on combinations followed per service was reached" in section


def test_failure_ends_and_reached_nodes(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        try_catch(
            [branch(case("A", invoke("x.api:a")), switch="/k")],
            [invoke("x.api:log")],
        ),
    )

    assert subject.service.flow_tree is not None
    branch_node = subject.logic.decision("D1").node_id
    try_node = subject.service.flow_tree.children[0].children[0].id
    assert subject.logic.failure_ends[branch_node][0] == try_node
    assert subject.lineage is not None
    assert branch_node in subject.lineage.reached_nodes


# --- outcomes after the audit ------------------------------------------------------------------


def test_a_loop_in_a_scenario_may_fail_on_a_missing_array(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(
            case("A", map_(set_("/t", "B")), loop(invoke("x.api:each"), in_array="/items")),
            switch="/k",
        ),
        branch(case("B", invoke("x.api:b")), switch="/t"),
    )

    table = subject.table("D1", "D2")
    first = table.scenarios[0]
    assert first.outcomes[0].case_ids == ("D1.c1",)
    assert len(first.loop_failures) == 1
    assert "fails instead if `/items` is missing (S29)" in subject.section()


def test_exit_flow_failure_in_a_scenario_skips_catch_and_finally(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(
            case("A", try_catch([exit_("$flow", "FAILURE")], [invoke("x.api:log")])),
            case("B", map_(set_("/t", "B"))),
            switch="/k",
        ),
        branch(case("B", invoke("x.api:b")), switch="/t"),
    )

    table = subject.table("D1", "D2")
    first = table.scenarios[0]
    assert first.outcomes[0].case_ids == ("D1.c1",)
    assert first.ends == ("E1",)
    assert first.outcomes[1].kind is OutcomeKind.NOT_REACHED
    row = next(line for line in subject.section().splitlines() if line.startswith("| P1 |"))
    assert "no CATCH or FINALLY runs (S33)" in row
    assert "assumption S14" in row


# --- assumptions ---------------------------------------------------------------------------


def test_assumed_rules_label_the_scenarios_from_the_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subject = _subject(
        tmp_path,
        branch(case("A", map_(copy("/maybe", "/t"))), switch="/k"),
        branch(case("B", invoke("x.api:b")), switch="/t"),
    )

    table = subject.table("D1", "D2")
    assert "S20" in table.scenarios[0].rules
    assert "assumption S20" in subject.section()
    flipped = replace(RULES_BY_ID["S20"], status=RuleStatus.VERIFIED)
    monkeypatch.setitem(RULES_BY_ID, "S20", flipped)
    assert "assumption S20" not in subject.section()
    labels = re.findall(r"assumption (S\d+(?:, S\d+)*)", subject.section())
    assert all(RULES_BY_ID[item].assumed for match in labels for item in match.split(", "))


# --- determinism and scale ----------------------------------------------------------------


def test_scenarios_are_deterministic(tmp_path: Path) -> None:
    first = _process_order(tmp_path / "a").text()
    second = _process_order(tmp_path / "b").text()

    assert first == second


@pytest.mark.slow
def test_scenarios_stay_fast_on_a_large_service(tmp_path: Path) -> None:
    steps = []
    for index in range(600):
        steps.append(map_(set_(f"/s{index % 50}", "A"), copy(f"/s{index % 50}", f"/t{index}")))
        steps.append(invoke(f"x.api:call{index}"))
        steps.append(
            branch(
                case("A", map_(set_(f"/s{(index + 1) % 50}", "B"))),
                case("$default", exit_("$parent")),
                switch=f"/t{index}",
            )
        )
    pkg = FlowPackage(tmp_path / "packages", "Scenario")
    pkg.service(SUBJECT, *steps)
    analysis = pkg.analyze()
    service = analysis.services[0]
    logic = compute_flow_logic(service)
    assert logic is not None
    lineage = compute_flow_lineage(service, logic)

    started = time.perf_counter()
    scenarios = compute_flow_scenarios(service, logic, lineage, {})
    elapsed = time.perf_counter() - started

    assert scenarios is not None
    assert elapsed < 10, elapsed
    assert all(len(table.decision_ids) <= MAX_CHAIN for table in scenarios.tables)


@pytest.mark.slow
def test_scenarios_stay_fast_on_a_long_chain(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path / "packages", "Scenario")
    pkg.service(SUBJECT, *_chain(600, ("/^a/", "/^b/", "/^c/")))
    service = pkg.analyze().services[0]
    logic = compute_flow_logic(service)
    assert logic is not None
    lineage = compute_flow_lineage(service, logic)

    started = time.perf_counter()
    scenarios = compute_flow_scenarios(service, logic, lineage, {})
    elapsed = time.perf_counter() - started

    assert scenarios is not None
    (table,) = scenarios.tables
    # The fields of the first 200 decisions are followed (flow_lineage.MAX_DECISIONS).
    assert table.truncated and table.left_out[0] == "D5" and table.left_out[-1] == "D200"
    assert elapsed < 10, elapsed
