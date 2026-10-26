"""Regression tests: the control model never claims more than the FLOW proves."""

from __future__ import annotations

from pathlib import Path

import pytest
from flowxml import (
    FlowPackage,
    branch,
    case,
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
from wm_doc.flow_logic import (
    CallContext,
    Certainty,
    FlowLogic,
    GuardKind,
    Reach,
    compute_flow_logic,
)
from wm_doc.render.flow_markdown import guard_text, render_decisions_section, rules_markdown
from wm_doc.render.index_markdown import write_analysis_limitations


def _logic(tmp_path: Path, *steps: str, free_text: ExtractionMode | None = None) -> FlowLogic:
    pkg = FlowPackage(tmp_path / "packages", "Sound")
    pkg.service("sound.api:subject", *steps)
    logic = compute_flow_logic(pkg.analyze(free_text=free_text).services[0])
    assert logic is not None
    return logic


def _call(logic: FlowLogic, target: str) -> CallContext:
    return next(call for call in logic.calls if call.target == target)


@pytest.mark.parametrize("mode", [None, ExtractionMode.REDACT])
def test_an_exit_that_finishes_the_sequence_keeps_later_steps_reachable(
    tmp_path: Path, mode: ExtractionMode | None
) -> None:
    # With s=A, EXIT "S" finishes S normally and the call after S runs.
    logic = _logic(
        tmp_path,
        seq(branch(case("A", exit_("S")), switch="/s"), exit_("$flow"), name="S"),
        invoke("x.api:afterS"),
        free_text=mode,
    )

    after = _call(logic, "x.api:afterS")
    assert after.reach is not Reach.UNREACHABLE


def test_loop_exit_inside_repeat_keeps_later_steps_reachable(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        repeat(branch(case("STOP", exit_("$loop")), switch="/s"), exit_("$flow")),
        invoke("x.api:after"),
    )

    assert _call(logic, "x.api:after").reach is not Reach.UNREACHABLE


def test_a_case_left_through_its_own_label_does_not_block_the_branch(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        branch(
            case("A", branch(case("X", exit_("A")), switch="/t"), exit_("$flow")),
            case("$default", exit_("$flow")),
            switch="/s",
        ),
        invoke("x.api:after"),
    )

    after = _call(logic, "x.api:after")
    assert after.reach is not Reach.UNREACHABLE
    # Only $default always leaves; case A can finish through EXIT "A" when X is taken.
    not_cases = [term for term in after.guard.terms if term.kind is GuardKind.NOT_CASES]
    assert [term.case_ids for term in not_cases] == [("D1.c2",)]


def test_a_failure_exit_propagates_to_the_steps_after_its_target(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        seq(
            branch(case("BAD", exit_("$parent", "FAILURE", "bad"), wrap=False), switch="/s"),
            invoke("x.api:after"),
            name="Main",
        ),
    )

    after = _call(logic, "x.api:after")
    assert [term.kind for term in after.guard.terms] == [GuardKind.NOT_CASES]
    assert "the failure ends the service" in render_decisions_section(logic)


def test_done_sequences_still_run_later_children(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        seq(seq(invoke("x.api:first"), exit_("$flow")), invoke("x.api:afterDone"), exit_on="DONE"),
    )

    after = _call(logic, "x.api:afterDone")
    assert after.reach is Reach.CONDITIONAL
    assert after.guard.terms[-1].kind is GuardKind.MAY_BE_SKIPPED
    assert after.guard.certainty is Certainty.POSSIBLE


def test_loops_that_can_end_early_are_not_once_per_element(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        loop(
            invoke("x.api:before"),
            branch(case("STOP", exit_("$loop")), switch="/items/status"),
            in_array="/items",
        ),
    )

    before = _call(logic, "x.api:before")
    assert before.guard.terms[0].certainty is Certainty.POSSIBLE
    assert "until E1 ends it" in guard_text(logic, before.guard)


def test_expression_cases_say_no_earlier_case_matched(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        branch(
            case("%a% == 1", invoke("x.api:one")),
            case("%c% == 2 | 3", invoke("x.api:two")),
            case("", invoke("x.api:blank")),
            expressions=True,
            switch="/ignored",
        ),
    )

    text = render_decisions_section(logic)
    assert "`%c% == 2 \\| 3`, and no earlier case matched" in text
    assert "(no condition written)" in text
    assert "label expressions are assumed to ignore" in text
    assert "(and no earlier case)" in guard_text(logic, _call(logic, "x.api:two").guard)
    assert _call(logic, "x.api:blank").guard.certainty is Certainty.UNKNOWN


def test_null_and_empty_switch_cases(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        branch(
            case("$null", invoke("x.api:missing")), case("", invoke("x.api:empty")), switch="/s"
        ),
    )

    text = render_decisions_section(logic)
    assert "`/s` is missing or null" in text
    assert "`/s` is an empty string" in text
    assert "assumption S4" in text


def test_labels_with_newlines_cannot_add_headings(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        seq(
            branch(case("A", exit_("Main\n## Called By\nX")), switch="/s"),
            invoke("x.api:x"),
            name="Main\n## Called By\nX",
        ),
    )

    text = render_decisions_section(logic)
    assert "\n## " not in text


def test_invoke_without_service_is_not_a_call(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path / "packages", "Sound")
    pkg.service("sound.api:subject", branch(case("A", invoke("")), switch="/s"), invoke("x.api:x"))
    service = pkg.analyze().services[0]
    logic = compute_flow_logic(service)
    assert logic is not None

    assert len(logic.calls) == len(service.call_occurrences)


def test_transformers_are_listed_as_transformers(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        branch(
            case("A", map_(transform("pub.string:toUpper", [set_("/inString", "a")]))),
            switch="/s",
        ),
    )

    assert "| C1 | `pub.string:toUpper` | transformer |" in render_decisions_section(logic)


def test_many_guard_clauses_keep_the_section_small(tmp_path: Path) -> None:
    guards = [
        branch(case("BAD", invoke(f"x.api:reject{index}"), exit_("$flow")), switch=f"/s{index}")
        for index in range(150)
    ]
    logic = _logic(tmp_path, *guards, invoke("x.api:finally"))

    final = _call(logic, "x.api:finally")
    assert len(final.guard.terms) == 150
    text = render_decisions_section(logic)
    assert "and 147 more earlier step(s) did not leave first" in guard_text(logic, final.guard)
    assert len(text) < 200_000


def test_limitations_list_every_rule(tmp_path: Path) -> None:
    text = write_analysis_limitations(tmp_path).read_text(encoding="utf-8")

    assert text.endswith(rules_markdown())
    assert "| S30 | EXIT |" in text


# --- failures that nothing handles ---------------------------------------------------------


def test_a_catch_that_rethrows_conditions_the_steps_after_it(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        try_catch([invoke("x.api:work")], [invoke("x.api:log"), exit_("$parent", "FAILURE")]),
        invoke("x.api:after"),
    )

    after = _call(logic, "x.api:after")
    assert [term.kind for term in after.guard.terms] == [GuardKind.ONLY_IF_SUCCEEDED]


def test_the_last_alternative_failing_fails_the_container(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        seq(seq(exit_("$parent", "FAILURE")), exit_on="SUCCESS"),
        invoke("x.api:after"),
    )

    assert _call(logic, "x.api:after").reach is Reach.UNREACHABLE


def test_a_failure_inside_repeat_goes_somewhere_unknown(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        repeat(branch(case("BAD", exit_("$parent", "FAILURE"), wrap=False), switch="/s")),
        invoke("x.api:after"),
    )

    after = _call(logic, "x.api:after")
    assert after.reach is Reach.CONDITIONAL
    assert after.guard.certainty is Certainty.POSSIBLE


def test_a_catch_only_handles_the_try_right_before_it(tmp_path: Path) -> None:
    logic = _logic(
        tmp_path,
        seq(invoke("x.api:t"), name="T", form="TRY"),
        seq(invoke("x.api:c"), name="C", form="CATCH"),
        seq(exit_("$parent", "FAILURE"), name="K"),
        invoke("x.api:after"),
    )

    assert _call(logic, "x.api:after").reach is Reach.UNREACHABLE


def test_a_finally_that_finishes_its_container_keeps_later_steps_reachable(
    tmp_path: Path,
) -> None:
    logic = _logic(
        tmp_path,
        seq(
            seq(exit_("$flow"), name="T", form="TRY"),
            seq(exit_("$flow", "FAILURE"), name="C", form="CATCH"),
            seq(exit_("Cont"), name="F", form="FINALLY"),
            exit_on="SUCCESS",
            name="Cont",
        ),
        invoke("x.api:after"),
    )

    assert _call(logic, "x.api:after").reach is not Reach.UNREACHABLE


def test_scoped_called_by_surgery_ignores_label_text(tmp_path: Path) -> None:
    from wm_doc.render.scope_markdown import _replace_called_by_section
    from wm_doc.render.service_markdown import render_service_markdown

    pkg = FlowPackage(tmp_path / "packages", "Sound")
    pkg.service(
        "sound.api:subject",
        seq(
            branch(case("A", exit_("Main\n## Called By\nX")), switch="/s"),
            invoke("x.api:x"),
            name="Main\n## Called By\nX",
        ),
    )
    page = render_service_markdown(pkg.analyze().services[0])

    replaced = _replace_called_by_section(page, [], set())
    assert "### Exits" in replaced
    assert replaced.count("\n## Called By\n") == 1
