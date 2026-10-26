"""Stage 1 of the conditional-flow work: which calls run under which conditions."""

from __future__ import annotations

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
    record,
    seq,
    set_,
    string,
    try_catch,
)

from wm_doc.analysis import analyze_path
from wm_doc.config import ExtractionMode, load_config
from wm_doc.flow_logic import (
    CallContext,
    Certainty,
    ConditionKind,
    FlowLogic,
    GuardKind,
    Reach,
    compute_flow_logic,
)
from wm_doc.flow_paths import PipelineRef, clean_path, expression_refs, path_ref
from wm_doc.ir import FlowService
from wm_doc.render.flow_markdown import guard_text, render_decisions_section
from wm_doc.render.service_markdown import render_service_markdown

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
ORDER_BATCH = "sample.orders.intake:validateOrderBatch"


def _service(tmp_path: Path, *steps: str, free_text: ExtractionMode | None = None) -> FlowService:
    pkg = FlowPackage(tmp_path / "packages", "Logic")
    pkg.service("logic.api:subject", *steps, inputs=[record("request", [string("status")])])
    return pkg.analyze(free_text=free_text).services[0]


def _logic(service: FlowService) -> FlowLogic:
    logic = compute_flow_logic(service)
    assert logic is not None
    return logic


def _call(logic: FlowLogic, target: str) -> CallContext:
    return next(call for call in logic.calls if call.target == target)


def _kinds(call: CallContext) -> list[tuple[GuardKind, str | None, tuple[str, ...]]]:
    return [(term.kind, term.decision_id, term.case_ids) for term in call.guard.terms]


def process_order(tmp_path: Path) -> FlowService:
    return _service(
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
    )


# --- paths ---------------------------------------------------------------------------------


def test_paths_are_normalised_without_guessing() -> None:
    assert clean_path("/key;4;0;doc:Type/userId;1;0") == "/key/userId"
    assert path_ref("/request;2;0/status;1;0") == PipelineRef(("request", "status"))
    assert path_ref("/verified") == PipelineRef(("verified",))
    assert path_ref("/orders[0];2;0/id;1;0") == PipelineRef(("orders[0]", "id"))
    assert path_ref("") is None
    assert PipelineRef(("orders[0]", "id")).overlaps(PipelineRef(("orders",)))
    assert not PipelineRef(("order",)).overlaps(PipelineRef(("orders",)))


def test_expression_references_ignore_percent_signs_inside_strings() -> None:
    assert expression_refs('%orders/status% == "CANCELLED"') == (PipelineRef(("orders", "status")),)
    assert expression_refs('%a% == "50%" and %b% != %a%') == (
        PipelineRef(("a",)),
        PipelineRef(("b",)),
    )
    assert expression_refs("%unterminated == 1") is None
    assert expression_refs('%a% == "open') is None


# --- decisions and call conditions ---------------------------------------------------------


def test_process_order_calls_belong_to_their_own_case_only(tmp_path: Path) -> None:
    logic = _logic(process_order(tmp_path))

    assert [decision.id for decision in logic.decisions] == ["D1", "D2"]
    first, second = logic.decisions
    assert first.switch == PipelineRef(("request", "status"))
    assert [case.condition.text for case in first.cases] == ["ACTIVE", "FINALIZED"]
    assert first.falls_through and not first.has_default
    assert [case.call_ids for case in first.cases] == [("C1",), ("C2",)]
    assert _kinds(_call(logic, "systemA:validateOrder")) == [(GuardKind.IN_CASE, "D1", ("D1.c1",))]
    assert _kinds(_call(logic, "systemB:finalizeOrder")) == [(GuardKind.IN_CASE, "D1", ("D1.c2",))]
    # The second decision is reached on every path: it inherits nothing from the first.
    assert second.guard.terms == ()
    assert _kinds(_call(logic, "systemC:activateOrder")) == [(GuardKind.IN_CASE, "D2", ("D2.c1",))]
    assert all(call.reach is Reach.CONDITIONAL for call in logic.calls)


def test_a_step_after_a_branch_never_inherits_its_case(tmp_path: Path) -> None:
    service = _service(
        tmp_path,
        branch(case("A", invoke("x.api:inA")), case("B", invoke("x.api:inB")), switch="/s"),
        invoke("x.api:after"),
    )
    logic = _logic(service)

    after = _call(logic, "x.api:after")
    assert after.guard.terms == ()
    assert after.reach is Reach.NORMAL


def test_nested_branches_stack_their_conditions(tmp_path: Path) -> None:
    inner = branch(
        case("EU", invoke("x.api:eu")), case("$default", invoke("x.api:rest")), switch="/region"
    )
    logic = _logic(_service(tmp_path, branch(case("ACTIVE", inner), switch="/request/status")))

    assert _kinds(_call(logic, "x.api:eu")) == [
        (GuardKind.IN_CASE, "D1", ("D1.c1",)),
        (GuardKind.IN_CASE, "D2", ("D2.c1",)),
    ]
    assert logic.decision("D2").guard.terms[0].case_ids == ("D1.c1",)
    rest = _call(logic, "x.api:rest")
    assert "D2 = otherwise" in guard_text(logic, rest.guard)
    assert "assumption S6" in render_decisions_section(logic)


def test_cases_that_exit_condition_the_steps_after_the_branch(tmp_path: Path) -> None:
    logic = _logic(
        _service(
            tmp_path,
            seq(
                branch(
                    case("OK", invoke("x.api:ok")),
                    case("$default", invoke("x.api:reject"), exit_("Main", "FAILURE", "bad")),
                    switch="/request/status",
                ),
                invoke("x.api:continue"),
                name="Main",
            ),
        )
    )

    following = _call(logic, "x.api:continue")
    assert _kinds(following) == [(GuardKind.NOT_CASES, "D1", ("D1.c2",))]
    assert following.guard.terms[0].exit_ids == ("E1",)
    assert logic.decision("D1").cases[1].ends_with == ("E1",)
    assert "D1 did not take D1.c2 (otherwise), which always leaves" in guard_text(
        logic, following.guard
    )


def test_an_exit_on_every_path_makes_later_steps_unreachable(tmp_path: Path) -> None:
    logic = _logic(
        _service(
            tmp_path,
            branch(
                case("A", exit_("$flow")),
                case("$default", exit_("$flow", "FAILURE", "no")),
                switch="/s",
            ),
            invoke("x.api:never"),
        )
    )

    assert _call(logic, "x.api:never").reach is Reach.UNREACHABLE
    assert logic.unreachable[0].exit_ids == ("E1", "E2")
    assert "Steps that never run" in render_decisions_section(logic)


def test_a_branch_without_default_can_fall_through(tmp_path: Path) -> None:
    logic = _logic(
        _service(tmp_path, branch(case("A", exit_("$flow")), switch="/s"), invoke("x.api:later"))
    )

    later = _call(logic, "x.api:later")
    assert later.reach is Reach.CONDITIONAL
    assert _kinds(later) == [(GuardKind.NOT_CASES, "D1", ("D1.c1",))]
    assert "no case matches" in render_decisions_section(logic)


def test_disabled_default_case_is_gone_and_the_branch_falls_through(tmp_path: Path) -> None:
    logic = _logic(
        _service(
            tmp_path,
            branch(
                case("A", invoke("x.api:a")),
                case("$default", invoke("x.api:b"), disabled=True),
                switch="/s",
            ),
        )
    )

    assert [case.condition.kind for case in logic.decision("D1").cases] == [ConditionKind.VALUE]
    assert logic.decision("D1").falls_through


def test_try_catch_and_alternatives(tmp_path: Path) -> None:
    logic = _logic(
        _service(
            tmp_path,
            try_catch(
                [invoke("x.api:work")],
                [invoke("pub.flow:getLastError"), exit_("$flow", "FAILURE", "failed")],
            ),
            invoke("x.api:afterwards"),
            seq(invoke("x.api:first"), invoke("x.api:second"), exit_on="SUCCESS"),
            seq(invoke("x.api:one"), invoke("x.api:two"), exit_on="DONE"),
        )
    )

    catch = _call(logic, "pub.flow:getLastError")
    assert catch.reach is Reach.FAILURE_PATH
    assert catch.guard.terms[0].kind is GuardKind.ON_FAILURE_OF
    assert "assumption S13, S14" in render_decisions_section(logic)
    afterwards = _call(logic, "x.api:afterwards")
    assert [term.kind for term in afterwards.guard.terms] == [GuardKind.ONLY_IF_SUCCEEDED]
    assert _call(logic, "x.api:second").guard.terms[-1].kind is GuardKind.ON_FAILURE_OF
    assert GuardKind.ON_FAILURE_OF not in {
        term.kind for term in _call(logic, "x.api:two").guard.terms
    }


def test_loops_exit_scopes_and_per_iteration_cases(tmp_path: Path) -> None:
    logic = _logic(
        _service(
            tmp_path,
            loop(
                branch(case("STOP", exit_("$loop")), switch="/items/status"),
                invoke("x.api:each"),
                in_array="/items",
                name="Each item",
            ),
            invoke("x.api:done"),
        )
    )

    each = _call(logic, "x.api:each")
    assert [term.kind for term in each.guard.terms] == [
        GuardKind.PER_ITERATION,
        GuardKind.NOT_CASES,
    ]
    assert logic.decision("D1").loop_id is not None
    exit_effect = logic.exits[0]
    assert logic.step_text[exit_effect.target_id or ""].startswith("the LOOP `Each item`")
    assert "S12" in exit_effect.rules
    # The loop exit ends the loop only: the step after the loop is not conditioned by it.
    assert _call(logic, "x.api:done").guard.terms == ()


def test_exit_parent_as_a_direct_case_leaves_the_branch(tmp_path: Path) -> None:
    logic = _logic(
        _service(
            tmp_path,
            branch(case("A", exit_("$parent"), wrap=False), switch="/s"),
            invoke("x.api:next"),
        )
    )

    assert logic.exits[0].target_id == logic.decision("D1").node_id
    assert _call(logic, "x.api:next").guard.terms == ()


def test_unknown_exit_labels_are_not_guessed(tmp_path: Path) -> None:
    logic = _logic(_service(tmp_path, seq(exit_("Nowhere"), name="Main"), invoke("x.api:x")))

    exit_effect = logic.exits[0]
    assert exit_effect.target_id is None
    assert exit_effect.certainty is Certainty.UNKNOWN
    assert exit_effect.note == "no enclosing step has that label"
    assert _call(logic, "x.api:x").guard.terms[0].kind is GuardKind.MAY_BE_SKIPPED


def test_duplicate_labels_default_not_last_and_patterns(tmp_path: Path) -> None:
    logic = _logic(
        _service(
            tmp_path,
            branch(
                case("$default", invoke("x.api:other")),
                case("A", invoke("x.api:first")),
                case("A", invoke("x.api:second")),
                case("/^B/", invoke("x.api:pattern")),
                switch="/s",
            ),
        )
    )

    decision = logic.decision("D1")
    assert decision.notes == ("DEFAULT_NOT_LAST", "DUPLICATE_LABEL")
    assert decision.cases[2].unreachable_rule == "S2"
    assert _call(logic, "x.api:second").reach is Reach.UNREACHABLE
    assert decision.cases[3].condition.kind is ConditionKind.PATTERN
    assert "assumption S5" in render_decisions_section(logic)


@pytest.mark.parametrize("mode", [ExtractionMode.REDACT, ExtractionMode.OMIT])
def test_withheld_labels_are_never_shown_as_empty_strings(
    tmp_path: Path, mode: ExtractionMode
) -> None:
    service = _service(
        tmp_path,
        branch(case("ACTIVE", invoke("x.api:a")), case("", invoke("x.api:b")), switch="/s"),
        free_text=mode,
    )
    logic = _logic(service)

    kinds = [case.condition.kind for case in logic.decision("D1").cases]
    assert kinds == [ConditionKind.WITHHELD, ConditionKind.EMPTY]
    text = render_decisions_section(logic)
    assert "(label withheld)" in text
    assert "ACTIVE" not in text
    assert 'is ""' not in text


def test_secret_like_labels_are_withheld(tmp_path: Path) -> None:
    service = _service(tmp_path, branch(case("TOKEN_EXPIRED", invoke("x.api:a")), switch="/s"))
    text = render_decisions_section(_logic(service))

    assert "TOKEN_EXPIRED" not in text
    assert "(label withheld)" in text


@pytest.mark.slow
def test_a_very_large_service_stays_fast(tmp_path: Path) -> None:
    import time

    steps = [
        branch(
            case("A", invoke(f"x.api:a{index}")),
            case("B", branch(case("C", exit_("$parent")), switch="/t"), invoke(f"x.api:b{index}")),
            case("$default", exit_("Main")),
            switch=f"/s{index}",
        )
        for index in range(600)
    ]
    service = _service(tmp_path, seq(*steps, name="Main"))
    started = time.perf_counter()
    logic = _logic(service)
    text = render_decisions_section(logic)
    elapsed = time.perf_counter() - started

    assert len(logic.decisions) == 1200
    assert len(logic.calls) == 1200
    assert "... and 1160 more decision(s) not shown." in text
    assert elapsed < 10


# --- the sample and the service page -------------------------------------------------------


def test_sample_order_batch_conditions() -> None:
    analysis = analyze_path(SAMPLES, load_config(None))
    service = next(s for s in analysis.services if s.identity.full_name == ORDER_BATCH)
    logic = _logic(service)

    assert len(logic.calls) == len(service.call_occurrences)
    assert {call.call_occurrence_id for call in logic.calls} == {
        call.id for call in service.call_occurrences
    }
    find = _call(logic, "sample.orders.services.order:findOrdersForValidation")
    assert _kinds(find) == [(GuardKind.NOT_CASES, "D1", ("D1.c2",))]
    get_order = _call(logic, "sample.orders.services.order:getOrder")
    assert [term.kind for term in get_order.guard.terms] == [
        GuardKind.NOT_CASES,
        GuardKind.PER_ITERATION,
        GuardKind.NOT_CASES,
    ]
    clear = _call(logic, "pub.flow:clearPipeline")
    assert [term.kind for term in clear.guard.terms] == [GuardKind.ONLY_IF_SUCCEEDED]
    assert _call(logic, "pub.flow:getLastError").reach is Reach.FAILURE_PATH
    repeated = [call for call in logic.calls if call.target.endswith(":checkErrorResult")]
    assert [call.same_target_as for call in repeated] == [(repeated[1].id,), (repeated[0].id,)]


def test_the_page_places_decisions_outside_the_load_bearing_block(tmp_path: Path) -> None:
    page = render_service_markdown(process_order(tmp_path))

    assert page.index("## Calls") < page.index("## Decisions") < page.index("## Called By")
    assert page.index("## Called By") < page.index("## Processes")
    assert "`/request/status` is `ACTIVE`" in page
    assert render_service_markdown(process_order(tmp_path / "again")) == page


def test_services_without_conditional_steps_get_no_section(tmp_path: Path) -> None:
    service = _service(tmp_path, map_(set_("/a", "b")), invoke("x.api:plain"))

    assert render_decisions_section(_logic(service)) == ""
    assert "## Decisions" not in render_service_markdown(service)
