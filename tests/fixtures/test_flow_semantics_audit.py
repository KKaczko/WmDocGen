"""The IS 10.15 FLOW semantics audit: rule statuses reach every page, and the changed meanings."""

from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

import pytest
from flowxml import (
    FlowPackage,
    branch,
    case,
    copy,
    exit_,
    invoke,
    loop,
    map_,
    repeat,
    seq,
    set_,
    transform,
    try_catch,
)

from wm_doc.config import ExtractionMode
from wm_doc.flow_lineage import FlowLineage, Origin, OriginKind, compute_flow_lineage
from wm_doc.flow_logic import (
    CallContext,
    Certainty,
    ExitScope,
    FlowLogic,
    GuardKind,
    Reach,
    compute_flow_logic,
)
from wm_doc.flow_semantics import RULES_BY_ID, RuleStatus, rule
from wm_doc.ir import AnalysisResult
from wm_doc.render.flow_markdown import render_decision_facts, render_decisions_section

SRC = Path(__file__).resolve().parents[2] / "src" / "wm_doc"
LABEL_RE = re.compile(r"assumption (S\d+(?:, S\d+)*)")


class Subject:
    """One analysed service with its control model, origins and rendered text."""

    def __init__(self, analysis: AnalysisResult) -> None:
        self.service = analysis.services[0]
        logic = compute_flow_logic(self.service)
        assert logic is not None
        self.logic: FlowLogic = logic
        self.lineage: FlowLineage | None = compute_flow_lineage(self.service, logic, {})

    def call(self, target: str) -> CallContext:
        return next(call for call in self.logic.calls if call.target == target)

    def origins(self, decision_id: str) -> list[Origin]:
        assert self.lineage is not None
        (variable,) = self.lineage.for_decision(decision_id)
        return [self.lineage.origin(origin_id) for origin_id in variable.origins]

    def kinds(self, decision_id: str) -> list[OriginKind]:
        return [origin.kind for origin in self.origins(decision_id)]

    def text(self) -> str:
        return render_decisions_section(self.logic, self.lineage)

    def facts(self) -> str:
        return render_decision_facts(self.logic, self.lineage)

    def line(self, needle: str, *, facts: bool = False) -> str:
        source = self.facts() if facts else self.text()
        return next(line for line in source.splitlines() if needle in line)


def _subject(tmp_path: Path, *steps: str, free_text: ExtractionMode | None = None) -> Subject:
    pkg = FlowPackage(tmp_path / "packages", "Audit")
    pkg.service("audit.api:subject", *steps)
    return Subject(pkg.analyze(free_text=free_text))


def _construct(
    wrapped: bool,
    try_steps: list[str],
    catch_steps: list[str],
    finally_steps: list[str] | None = None,
) -> list[str]:
    """TRY/CATCH(/FINALLY) inside an EXIT-ON SUCCESS sequence, or as plain siblings (S14)."""
    if wrapped:
        return [try_catch(try_steps, catch_steps, finally_steps)]
    blocks = [
        seq(*try_steps, name="Try", form="TRY"),
        seq(*catch_steps, name="Catch", form="CATCH"),
    ]
    if finally_steps is not None:
        blocks.append(seq(*finally_steps, name="Finally", form="FINALLY"))
    return blocks


FORMS = pytest.mark.parametrize("wrapped", [True, False], ids=["wrapped", "siblings"])


# --- S7, S31: no case matched ---------------------------------------------------------------


def test_a_missing_switch_without_null_or_default_is_never_a_certain_success(
    tmp_path: Path,
) -> None:
    subject = _subject(
        tmp_path, branch(case("A", invoke("x.api:a")), switch="/s"), invoke("x.api:after")
    )

    decision = subject.logic.decision("D1")
    assert decision.falls_through
    assert decision.missing_fails
    row = subject.line("no case matches")
    assert "(S7)" in row
    assert "`/s` is missing the BRANCH fails instead (S31)" in row
    assert "fails" in subject.line("no case matches", facts=True)


@pytest.mark.parametrize("label", ["$null", "$default"])
def test_a_null_or_default_case_takes_a_missing_switch(tmp_path: Path, label: str) -> None:
    subject = _subject(
        tmp_path,
        branch(case("A", invoke("x.api:a")), case(label, invoke("x.api:other")), switch="/s"),
    )

    decision = subject.logic.decision("D1")
    assert not decision.missing_fails
    assert "the BRANCH fails" not in subject.text()
    assert "the BRANCH fails" not in subject.facts()


def test_label_expressions_do_not_fail_for_a_missing_field(tmp_path: Path) -> None:
    subject = _subject(tmp_path, branch(case("%s% == 'A'", invoke("x.api:a")), expressions=True))

    decision = subject.logic.decision("D1")
    assert decision.falls_through
    assert not decision.missing_fails


def test_withheld_labels_may_hide_a_null_case(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(case("A", invoke("x.api:a")), switch="/s"),
        free_text=ExtractionMode.REDACT,
    )

    assert subject.logic.decision("D1").missing_fails
    row = subject.line("no case matches")
    assert "fails instead, unless a withheld label is `$null`" in row


# --- S29: LOOP over a missing array ---------------------------------------------------------


@FORMS
def test_a_missing_in_array_is_never_a_zero_iteration_success(
    tmp_path: Path, wrapped: bool
) -> None:
    subject = _subject(
        tmp_path,
        *_construct(
            wrapped,
            [loop(map_(set_("/x", "A")), in_array="/items")],
            [branch(case("A", invoke("x.api:undo")), switch="/x")],
        ),
    )

    # The LOOP fails when /items is missing, so the CATCH runs, before any iteration.
    assert subject.call("x.api:undo").reach is Reach.FAILURE_PATH
    assert OriginKind.CALLER in subject.kinds("D1")
    assert "fail" in rule("S29").statement


# --- S13, S33, S34, S35: TRY, CATCH and FINALLY -----------------------------------------------


@FORMS
def test_exit_flow_failure_in_try_makes_no_catch_or_finally_call_reachable(
    tmp_path: Path, wrapped: bool
) -> None:
    subject = _subject(
        tmp_path,
        *_construct(
            wrapped, [exit_("$flow", "FAILURE")], [invoke("x.api:log")], [invoke("x.api:cleanup")]
        ),
        invoke("x.api:after"),
    )

    for target in ("x.api:log", "x.api:cleanup", "x.api:after"):
        assert subject.call(target).reach is Reach.UNREACHABLE, target
    assert "S33" in subject.call("x.api:cleanup").unreachable_rules
    never = subject.text().split("### Steps that never run")[1]
    assert "the CATCH block `Catch`" in never
    assert "the FINALLY block `Finally`" in never


@FORMS
def test_a_try_that_may_fail_first_keeps_catch_and_finally(tmp_path: Path, wrapped: bool) -> None:
    subject = _subject(
        tmp_path,
        *_construct(
            wrapped,
            [invoke("x.api:work"), exit_("$flow", "FAILURE")],
            [invoke("x.api:log")],
            [invoke("x.api:cleanup")],
        ),
        invoke("x.api:after"),
    )

    assert subject.call("x.api:log").reach is Reach.FAILURE_PATH
    assert subject.call("x.api:cleanup").reach is not Reach.UNREACHABLE
    # work fails, the CATCH finishes, FINALLY runs and the service goes on.
    assert subject.call("x.api:after").reach is not Reach.UNREACHABLE


@FORMS
def test_a_success_exit_from_try_still_runs_finally(tmp_path: Path, wrapped: bool) -> None:
    subject = _subject(
        tmp_path,
        *_construct(wrapped, [exit_("$flow")], [invoke("x.api:log")], [invoke("x.api:cleanup")]),
    )

    assert subject.call("x.api:cleanup").reach is not Reach.UNREACHABLE
    # Nothing in the TRY can fail, so its CATCH never runs.
    assert subject.call("x.api:log").reach is Reach.UNREACHABLE


def test_a_catch_after_a_try_that_always_leaves_still_handles_its_failures(
    tmp_path: Path,
) -> None:
    subject = _subject(
        tmp_path,
        *_construct(False, [invoke("x.api:work"), exit_("$flow")], [invoke("x.api:log")]),
        invoke("x.api:after"),
    )

    assert subject.call("x.api:log").reach is Reach.FAILURE_PATH
    assert subject.call("x.api:after").reach is not Reach.UNREACHABLE


@FORMS
def test_a_catch_filter_may_let_a_failure_through(tmp_path: Path, wrapped: bool) -> None:
    steps = _construct(wrapped, [exit_("$parent", "FAILURE")], [invoke("x.api:log")])
    filtered = [
        item.replace('FORM="CATCH"', 'FORM="CATCH" SELECTION="INCLUDE"', 1) for item in steps
    ]
    subject = _subject(tmp_path, *filtered, invoke("x.api:after"))

    effect = subject.logic.exits[0]
    assert effect.reach_id is None
    assert "S35" in effect.rules
    assert subject.call("x.api:log").reach is Reach.FAILURE_PATH


# --- S11, S12: EXIT $iteration ---------------------------------------------------------------


def test_exit_iteration_ends_only_the_current_iteration(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        loop(
            map_(set_("/t", "A")),
            branch(case("K", map_(set_("/t", "B")), exit_("$iteration")), switch="/k"),
            branch(case("A", invoke("x.api:each")), switch="/t"),
            in_array="/items",
        ),
        invoke("x.api:after"),
    )

    effect = subject.logic.exits[0]
    assert effect.scope is ExitScope.ITERATION
    assert effect.target_id is not None
    assert effect.certainty is Certainty.DERIVED
    each = subject.call("x.api:each")
    per = next(term for term in each.guard.terms if term.kind is GuardKind.PER_ITERATION)
    assert per.exit_ids == ()
    assert per.certainty is Certainty.DERIVED
    assert [origin.value for origin in subject.origins("D2")] == ["A"]
    assert "ends the current iteration of the LOOP" in subject.text()
    assert subject.call("x.api:after").reach is Reach.NORMAL


def test_exit_iteration_with_failure_is_not_resolved(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        loop(branch(case("K", exit_("$iteration", "FAILURE")), switch="/k"), in_array="/items"),
    )

    effect = subject.logic.exits[0]
    assert effect.target_id is None
    assert effect.certainty is Certainty.UNKNOWN
    assert effect.note is not None and "FAILURE" in effect.note


# --- S36: first-level rollback -------------------------------------------------------------


def _on_x() -> str:
    return branch(case("A", invoke("x.api:again")), switch="/x")


def test_a_failed_alternative_rolls_back_first_level_fields(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        seq(seq(map_(set_("/x", "A")), invoke("x.api:send")), _on_x(), exit_on="SUCCESS"),
    )

    assert subject.kinds("D1") == [OriginKind.CALLER]


def test_nested_fields_may_keep_their_changes_after_a_rollback(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        seq(
            seq(map_(set_("/doc/x", "A")), invoke("x.api:send")),
            branch(case("A", invoke("x.api:again")), switch="/doc/x"),
            exit_on="SUCCESS",
        ),
    )

    assert subject.kinds("D1") == [OriginKind.SET, OriginKind.CALLER]


def test_a_done_sequence_rolls_back_a_failed_child(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        seq(seq(map_(set_("/x", "A")), exit_("$parent", "FAILURE")), _on_x(), exit_on="DONE"),
    )

    assert subject.kinds("D1") == [OriginKind.CALLER]


@pytest.mark.parametrize(
    ("loop_on", "kinds"),
    [("FAILURE", [OriginKind.CALLER]), ("SUCCESS", [OriginKind.SET, OriginKind.CALLER])],
)
def test_a_repeat_on_failure_starts_each_attempt_from_rolled_back_fields(
    tmp_path: Path, loop_on: str, kinds: list[OriginKind]
) -> None:
    subject = _subject(
        tmp_path,
        repeat(_on_x(), map_(set_("/x", "A")), invoke("x.api:send"), loop_on=loop_on),
    )

    assert subject.kinds("D1") == kinds


def test_a_try_does_not_roll_back_for_its_catch(tmp_path: Path) -> None:  # S15
    subject = _subject(
        tmp_path, try_catch([map_(set_("/x", "A")), invoke("x.api:send")], [_on_x()])
    )

    assert subject.kinds("D1") == [OriginKind.SET, OriginKind.CALLER]


# --- S10: a MAP that succeeds may not end an EXIT-ON SUCCESS sequence -----------------------


def test_a_later_alternative_may_also_run_after_a_map_succeeded(tmp_path: Path) -> None:
    subject = _subject(tmp_path, seq(map_(set_("/x", "A")), _on_x(), exit_on="SUCCESS"))

    term = subject.call("x.api:again").guard.terms[0]
    assert term.kind is GuardKind.ON_FAILURE_OF
    assert term.certainty is Certainty.POSSIBLE
    assert subject.kinds("D1") == [OriginKind.SET, OriginKind.CALLER]


# --- S18: transformers --------------------------------------------------------------------


def test_a_transformer_without_linked_outputs_never_runs(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(transform("x.api:silent", [set_("/inString", "a")])),
        map_(transform("x.api:linked", [], [copy("/value", "/out")])),
        branch(case("A", invoke("x.api:a")), switch="/s"),
    )

    silent = subject.call("x.api:silent")
    assert silent.reach is Reach.UNREACHABLE
    assert silent.unreachable_rules == ("S18",)
    assert subject.call("x.api:linked").reach is Reach.NORMAL
    assert "no output is linked" in subject.line("x.api:silent")


# --- S8, S37: labels that never match ------------------------------------------------------


def test_label_expressions_ignore_null_and_blank_labels(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(
            case("%a% == 1", invoke("x.api:one")),
            case("$null", invoke("x.api:null")),
            case("", invoke("x.api:blank")),
            expressions=True,
        ),
    )

    for target in ("x.api:null", "x.api:blank"):
        call = subject.call(target)
        assert call.reach is Reach.UNREACHABLE, target
        assert call.unreachable_rules == ("S8",)
    assert subject.call("x.api:one").reach is Reach.CONDITIONAL
    assert "label expressions ignore" in subject.text()


def test_a_repeated_label_never_runs_by_assumption(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(case("A", invoke("x.api:first")), case("A", invoke("x.api:second")), switch="/s"),
    )

    assert subject.logic.decision("D1").cases[1].unreachable_rule == "S37"
    assert "assumption S37" in subject.text()


# --- review regressions -------------------------------------------------------------------


def test_a_change_through_a_linked_document_is_possible_on_both_sides(tmp_path: Path) -> None:
    forward = _subject(
        tmp_path / "forward",
        map_(set_("/a/f", "old")),
        map_(copy("/a;2;0", "/b;2;0")),
        map_(set_("/a/f", "changed")),
        branch(case("old", invoke("x.api:x")), switch="/b/f"),
    )
    backward = _subject(
        tmp_path / "backward",
        map_(copy("/a;2;0", "/b;2;0")),
        map_(set_("/b/f", "changed")),
        branch(case("old", invoke("x.api:x")), switch="/a/f"),
    )

    (variable,) = forward.lineage.for_decision("D1") if forward.lineage else ()
    assert not variable.unique
    assert OriginKind.LINKED in forward.kinds("D1")
    linked = next(item for item in forward.origins("D1") if item.kind is OriginKind.LINKED)
    assert "S38" in linked.rules
    assert "a document linked to this one (S38)" in forward.text()
    assert backward.kinds("D1") == [OriginKind.LINKED, OriginKind.CALLER]


def test_a_value_copy_of_a_string_is_not_linked(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        map_(set_("/a", "old")),
        map_(copy("/a", "/b")),
        map_(set_("/a", "changed")),
        branch(case("old", invoke("x.api:x")), switch="/b"),
    )

    assert subject.kinds("D1") == [OriginKind.COPY]


@pytest.mark.parametrize("wrapped_in_try", [True, False])
def test_an_empty_exit_on_success_sequence_finishes(tmp_path: Path, wrapped_in_try: bool) -> None:
    empty = seq(invoke("x.api:off", disabled=True), exit_on="SUCCESS")
    if wrapped_in_try:
        steps = [
            seq(empty, name="T", form="TRY"),
            seq(invoke("x.api:c"), name="C", form="CATCH"),
            seq(invoke("x.api:f"), name="F", form="FINALLY"),
        ]
    else:
        steps = [empty]
    subject = _subject(tmp_path, *steps, invoke("x.api:after"), _on_x())

    assert subject.call("x.api:after").reach is not Reach.UNREACHABLE
    if wrapped_in_try:
        assert subject.call("x.api:f").reach is not Reach.UNREACHABLE
    assert subject.lineage is not None
    assert subject.lineage.for_decision("D1")[0].reached


def test_a_failing_finally_in_a_done_sequence_keeps_its_partial_changes(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        seq(
            seq(invoke("x.api:t"), name="T", form="TRY"),
            seq(
                map_(set_("/d/s", "two")),
                invoke("x.api:f"),
                map_(set_("/d/s", "three")),
                name="F",
                form="FINALLY",
            ),
            branch(case("three", invoke("x.api:x")), switch="/d/s"),
            exit_on="DONE",
        ),
    )

    assert [origin.value for origin in subject.origins("D1")] == ["two", "three", None]


def test_steps_after_an_exiting_case_in_a_done_sequence_claim_nothing_about_it(
    tmp_path: Path,
) -> None:
    subject = _subject(
        tmp_path,
        seq(
            branch(case("A", invoke("x.api:inA"), exit_("$flow")), switch="/s"),
            invoke("x.api:after"),
            exit_on="DONE",
        ),
    )

    kinds = [term.kind for term in subject.call("x.api:after").guard.terms]
    assert kinds == [GuardKind.MAY_BE_SKIPPED]


def test_a_finally_belongs_to_its_try_among_other_alternatives(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        seq(
            invoke("x.api:a"),
            seq(invoke("x.api:t"), name="T", form="TRY"),
            seq(exit_("$flow"), name="F", form="FINALLY"),
            exit_on="SUCCESS",
        ),
        invoke("x.api:after"),
    )

    assert subject.call("x.api:after").reach is not Reach.UNREACHABLE


def test_cases_that_never_run_by_assumption_still_feed_the_origins(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(
            case("A", map_(set_("/t", "one"))),
            case("A", map_(set_("/t", "two"))),
            case("$default", exit_("$flow")),
            switch="/s",
        ),
        branch(case("one", invoke("x.api:x")), switch="/t"),
    )

    assert sorted(origin.value or "" for origin in subject.origins("D2")) == ["one", "two"]


def test_an_alternative_after_a_map_is_not_a_failure_path_only(tmp_path: Path) -> None:
    subject = _subject(tmp_path, seq(map_(set_("/x", "A")), _on_x(), exit_on="SUCCESS"))

    again = subject.call("x.api:again")
    assert again.reach is Reach.CONDITIONAL
    assert "failed, or did not end the sequence" in subject.line("| C1 |")


def test_a_failing_catch_is_not_handled_by_the_next_catch(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        seq(
            seq(invoke("x.api:t"), name="T", form="TRY"),
            seq(exit_("$parent", "FAILURE"), name="C1", form="CATCH"),
            seq(invoke("x.api:c2"), name="C2", form="CATCH"),
            exit_on="SUCCESS",
        ),
    )

    effect = subject.logic.exits[0]
    assert effect.reach_id != effect.target_id
    assert "S35" in effect.rules


def test_a_second_default_never_runs_by_assumption(tmp_path: Path) -> None:
    subject = _subject(
        tmp_path,
        branch(
            case("$default", invoke("x.api:one")),
            case("$default", invoke("x.api:two")),
            switch="/s",
        ),
    )

    assert subject.logic.decision("D1").cases[1].unreachable_rule == "S37"


# --- labels come from the registry --------------------------------------------------------


def _everything(tmp_path: Path) -> Subject:
    """One service touching most rules, for the label checks."""
    scoped = seq(
        map_(set_("/t", "B")), branch(case("B", invoke("x.api:inner")), switch="/t")
    ).replace("<SEQUENCE", '<SEQUENCE SCOPE="/doc"', 1)
    return _subject(
        tmp_path,
        branch(
            case("$default", invoke("x.api:other")),
            case("A", invoke("x.api:first")),
            case("A", invoke("x.api:again")),
            case("/^B/", invoke("x.api:pattern")),
            switch="/s",
        ),
        map_(set_("/v", "A"), copy("/w", "/v")),
        branch(case("A", invoke("x.api:v")), switch="/v"),
        branch(case("A", invoke("x.api:t")), switch="/t"),
        scoped,
        try_catch([invoke("x.api:work")], [invoke("x.api:log")], [invoke("x.api:cleanup")]),
        seq(seq(exit_("$parent", "FAILURE")), invoke("x.api:second"), exit_on="SUCCESS"),
        loop(branch(case("K", exit_("$iteration")), switch="/k"), in_array="/items"),
        branch(
            case("%a% == 1", invoke("x.api:one")), case("", invoke("x.api:blank")), expressions=True
        ),
        branch(case("Z", invoke("x.api:z")), switch="/z"),
        invoke("x.api:end"),
    )


def test_rendered_assumption_labels_name_only_assumed_rules(tmp_path: Path) -> None:
    subject = _everything(tmp_path)
    text = subject.text() + "\n" + subject.facts()

    named = {rule_id for match in LABEL_RE.finditer(text) for rule_id in match[1].split(", ")}
    assert named
    assert all(rule(rule_id).assumed for rule_id in named), named


def test_a_status_change_changes_every_label(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subject = _everything(tmp_path)
    before = subject.text()
    assert "assumption S19" in before
    assert "assumption S37" in before
    for rule_id in ("S6", "S7", "S24", "S31"):
        assert not re.search(rf"assumption (S\d+, )*{rule_id}\b", before), rule_id

    for rule_id, status in [
        ("S19", RuleStatus.DOCUMENTED),
        ("S37", RuleStatus.VERIFIED),
        ("S6", RuleStatus.ASSUMED),
        ("S7", RuleStatus.ASSUMED),
        ("S24", RuleStatus.ASSUMED),
        ("S31", RuleStatus.ASSUMED),
    ]:
        monkeypatch.setitem(RULES_BY_ID, rule_id, replace(RULES_BY_ID[rule_id], status=status))
    after = subject.text()

    assert "assumption S19" not in after
    assert "assumption S37" not in after
    for rule_id in ("S6", "S7", "S24", "S31"):
        assert re.search(rf"assumption (S\d+, )*{rule_id}\b", after), rule_id


def test_a_status_change_never_changes_the_facts_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from wm_doc.describer import deterministic_facts, render_facts_block
    from wm_doc.effects import compute_service_facts

    pkg = FlowPackage(tmp_path / "packages", "Audit")
    pkg.service(
        "audit.api:subject",
        branch(case("A", invoke("x.api:a")), case("A", invoke("x.api:b")), switch="/s"),
        map_(set_("/v", "A"), copy("/w", "/v")),
        branch(case("A", invoke("x.api:v")), switch="/v"),
    )
    analysis = pkg.analyze()
    service = analysis.services[0]
    facts = compute_service_facts(analysis)[service.identity.full_name]

    def snapshot() -> tuple[str, str]:
        hashed = deterministic_facts(service, facts, {}, lambda _name: None)
        return hashed, render_facts_block(service, facts)

    hashed, block = snapshot()
    for rule_id in RULES_BY_ID:
        flipped = RuleStatus.DOCUMENTED if rule(rule_id).assumed else RuleStatus.ASSUMED
        monkeypatch.setitem(RULES_BY_ID, rule_id, replace(RULES_BY_ID[rule_id], status=flipped))

    assert snapshot() == (hashed, block)
    assert "### Decisions" in block


def test_no_text_names_an_assumption_by_hand() -> None:
    offenders = [
        f"{path.relative_to(SRC)}:{number}"
        for path in sorted(SRC.rglob("*.py"))
        if path.name != "flow_semantics.py"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"assumption S\d", line)
    ]

    assert offenders == []
