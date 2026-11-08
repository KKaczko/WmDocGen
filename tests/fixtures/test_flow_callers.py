"""Stage 7 of the conditional-flow work: conservative facts across services.

- What a called service may write to the pipeline, bottom-up; anything not known (a platform
  call, a service outside the packages, a dynamic call, a cycle) makes it "unknown".
- Decision inputs: fields a decision tests that the service does not set before it.
- What each direct caller passes into them, read from the caller's own FLOW just before the
  call; a single literal with nothing in between can leave only one case possible.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flowxml import FlowPackage, branch, case, copy, invoke, loop, map_, set_, string, transform

from wm_doc.flow_callers import (
    MAX_CALLERS,
    DecisionInput,
    PassKind,
    compute_decision_inputs,
    compute_pipeline_writes,
)
from wm_doc.flow_lineage import compute_flow_lineage
from wm_doc.flow_logic import compute_flow_logic
from wm_doc.ir import AnalysisResult, FlowService
from wm_doc.render.flow_markdown import render_decisions_section

ROUTE = "calls.api:route"


def _server(root: Path, *, extra_cases: list[str] | None = None) -> AnalysisResult:
    pkg = FlowPackage(root, "Calls")
    pkg.service(
        ROUTE,
        branch(
            case("ACTIVE", invoke("calls.api:onActive")),
            case("CLOSED", invoke("calls.api:onClosed")),
            *[case(label, invoke("calls.api:onOther")) for label in extra_cases or []],
            case("$default", invoke("calls.api:onDefault")),
            switch="/status",
        ),
        inputs=[string("status")],
    )
    pkg.service("calls.api:fromActive", invoke(ROUTE, inputs=[set_("/status", "ACTIVE")]))
    pkg.service("calls.api:fromOther", map_(set_("/status", "OTHER")), invoke(ROUTE))
    pkg.service("calls.api:fromRequest", invoke(ROUTE, inputs=[copy("/request/state", "/status")]))
    pkg.service("calls.api:passThrough", invoke(ROUTE))
    pkg.service(
        "calls.api:unknownBetween",
        map_(set_("/status", "ACTIVE")),
        invoke("ext.api:other"),
        invoke(ROUTE),
    )
    pkg.service("calls.api:helper", map_(set_("/other", "x")))
    pkg.service("calls.api:writesStatus", map_(set_("/status", "CLOSED")))
    pkg.service("calls.api:helpers", invoke("calls.api:helper"), invoke("calls.api:writesStatus"))
    pkg.service(
        "calls.api:helperBetween",
        map_(set_("/status", "ACTIVE")),
        invoke("calls.api:helper"),
        invoke(ROUTE),
    )
    pkg.service(
        "calls.api:writerBetween",
        map_(set_("/status", "ACTIVE")),
        invoke("calls.api:writesStatus"),
        invoke(ROUTE),
    )
    return pkg.analyze()


def _by_name(analysis: AnalysisResult) -> dict[str, FlowService]:
    return {service.identity.full_name: service for service in analysis.services}


def _inputs(analysis: AnalysisResult, name: str = ROUTE) -> tuple[DecisionInput, ...]:
    services = _by_name(analysis)
    service = services[name]
    logic = compute_flow_logic(service)
    writes = compute_pipeline_writes(analysis.services)
    signatures = {item.identity.full_name: item.signature for item in analysis.services}
    lineage = compute_flow_lineage(service, logic, signatures, writes=writes)
    callers = [
        item
        for item in analysis.services
        if any(call.target == name for call in item.call_occurrences)
    ]
    return compute_decision_inputs(
        service, logic, lineage, callers=callers, signatures=signatures, writes=writes
    )


# --- what a called service writes ---------------------------------------------------------------


def test_write_summaries_are_known_only_when_every_step_is_analysed(tmp_path: Path) -> None:
    writes = compute_pipeline_writes(_server(tmp_path).services)

    helper = writes["calls.api:helper"]
    assert not helper.unknown and helper.fields == frozenset({("other",)})
    assert writes["calls.api:writesStatus"].may_change(("status",))
    assert not helper.may_change(("status",))
    # It calls services outside the packages, so anything may change.
    assert writes[ROUTE].unknown and writes[ROUTE].may_change(("anything",))
    # A service's summary includes what its callees write; one calling `route` is unknown.
    assert writes["calls.api:helpers"].fields == {("status",), ("other",)}
    assert writes["calls.api:helperBetween"].unknown


def test_a_cycle_or_a_platform_call_makes_a_summary_unknown(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Cycle")
    pkg.service("cycle.api:a", map_(set_("/x", "1")), invoke("cycle.api:b"))
    pkg.service("cycle.api:b", invoke("cycle.api:a"))
    pkg.service("cycle.api:logs", invoke("pub.flow:debugLog"))

    writes = compute_pipeline_writes(pkg.analyze().services)

    assert writes["cycle.api:a"].unknown and writes["cycle.api:b"].unknown
    assert writes["cycle.api:logs"].unknown


def test_a_call_that_cannot_write_the_field_is_not_a_call_in_between(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Between")
    pkg.service("b.api:helper", map_(set_("/other", "x")))
    pkg.service(
        "b.api:decides",
        map_(set_("/s", "A")),
        invoke("b.api:helper"),
        branch(case("A", invoke("b.api:x")), switch="/s"),
    )
    analysis = pkg.analyze()
    service = _by_name(analysis)["b.api:decides"]
    logic = compute_flow_logic(service)
    signatures = {item.identity.full_name: item.signature for item in analysis.services}

    without = compute_flow_lineage(service, logic, signatures)
    tightened = compute_flow_lineage(
        service, logic, signatures, writes=compute_pipeline_writes(analysis.services)
    )

    assert without is not None and tightened is not None
    assert without.variables[0].calls_in_between == ("C1",)
    assert tightened.variables[0].calls_in_between == ()
    assert tightened.variables[0].unique


# --- decision inputs and what callers pass ------------------------------------------------------


def test_a_field_only_the_caller_sets_is_a_decision_input(tmp_path: Path) -> None:
    inputs = _inputs(_server(tmp_path))

    assert [(item.path.text(), item.decision_ids, item.declared) for item in inputs] == [
        ("/status", ("D1",), True)
    ]


def test_each_caller_says_what_it_passes(tmp_path: Path) -> None:
    (status,) = _inputs(_server(tmp_path))

    passes = {item.caller: item for item in status.passes}

    assert passes["calls.api:fromActive"].kind is PassKind.VALUE
    assert passes["calls.api:fromActive"].cases == {"D1": ("D1.c1",)}
    assert passes["calls.api:fromOther"].cases == {"D1": ("D1.c3",)}  # only $default
    assert passes["calls.api:fromRequest"].kind is PassKind.SET_OR_COPY
    assert passes["calls.api:fromRequest"].cases is None
    assert passes["calls.api:passThrough"].kind is PassKind.THROUGH
    # A call in between that may change it: no conclusion, and it is named.
    unknown = passes["calls.api:unknownBetween"]
    assert unknown.cases is None and unknown.calls_between == ("C1",)
    # A helper that is proven not to write it does not stop the conclusion; one that does.
    assert passes["calls.api:helperBetween"].cases == {"D1": ("D1.c1",)}
    assert passes["calls.api:writerBetween"].cases is None
    assert status.callers_hidden == 0


def test_no_case_is_concluded_from_a_pattern(tmp_path: Path) -> None:
    (status,) = _inputs(_server(tmp_path, extra_cases=["/^ACT.*/"]))

    passes = {item.caller: item for item in status.passes}

    assert passes["calls.api:fromActive"].kind is PassKind.VALUE
    assert passes["calls.api:fromActive"].cases is None


def test_a_field_the_service_sets_itself_is_not_a_decision_input(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Own")
    pkg.service(
        "own.api:route",
        map_(set_("/status", "A")),
        branch(case("A", invoke("own.api:x")), switch="/status"),
    )
    pkg.service("own.api:caller", invoke("own.api:route", inputs=[set_("/status", "B")]))

    assert _inputs(pkg.analyze(), "own.api:route") == ()


def test_a_decision_inside_a_loop_gets_no_conclusion(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Loop")
    pkg.service(
        "loop.api:route",
        loop(branch(case("A", invoke("loop.api:x")), switch="/items/kind"), in_array="/items"),
    )
    pkg.service("loop.api:caller", invoke("loop.api:route", inputs=[set_("/items/kind", "A")]))

    inputs = _inputs(pkg.analyze(), "loop.api:route")

    assert inputs
    assert all(item.cases is None for field in inputs for item in field.passes)


def test_callers_are_capped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import wm_doc.flow_callers as flow_callers

    monkeypatch.setattr(flow_callers, "MAX_CALLERS", 3)
    (status,) = _inputs(_server(tmp_path))

    assert len({item.caller for item in status.passes}) == 3
    assert status.callers_hidden == 4
    assert MAX_CALLERS == 50


def test_a_java_service_is_never_summarized(tmp_path: Path) -> None:
    from wm_doc.analysis import analyze_path
    from wm_doc.config import load_config
    from wm_doc.explorer.synthetic import write_demo_packages

    write_demo_packages(tmp_path)
    services = analyze_path(tmp_path, load_config(None), None, processes_file_explicit=False)

    # The Java reader does not record every API that changes the pipeline.
    assert compute_pipeline_writes(services.services)["orders.api.routing:routeOrder"].unknown


def test_a_change_through_a_linked_document_keeps_the_call_in_between(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Linked")
    pkg.service(
        "l.api:route",
        branch(case("A", invoke("l.api:x")), case("B", invoke("l.api:y")), switch="/x/status"),
    )
    pkg.service("l.api:setsY", map_(set_("/y/status", "B")))
    pkg.service(
        "l.api:caller",
        map_(copy("/x", "/y")),  # /x and /y now share one document (S38)
        map_(set_("/x/status", "A")),
        invoke("l.api:setsY"),
        invoke("l.api:route"),
    )

    (field,) = _inputs(pkg.analyze(), "l.api:route")

    (passed,) = field.passes
    assert passed.cases is None and passed.calls_between == ("C1",)


def test_an_empty_literal_decides_only_an_empty_case(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Empty")
    pkg.service(
        "e.api:route",
        branch(case("A", invoke("e.api:a")), case("$default", invoke("e.api:d")), switch="/s"),
    )
    pkg.service("e.api:caller", invoke("e.api:route", inputs=[set_("/s", "")]))

    (field,) = _inputs(pkg.analyze(), "e.api:route")

    assert [item.cases for item in field.passes] == [None]


def test_a_transformer_caller_is_listed_as_not_read(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Transformer")
    pkg.service(
        "t.api:route",
        branch(case("A", invoke("t.api:a")), switch="/s"),
        outputs=[string("out")],
    )
    pkg.service(
        "t.api:caller",
        map_(transform("t.api:route", outputs=[copy("/out", "/result")])),
    )

    (field,) = _inputs(pkg.analyze(), "t.api:route")

    assert [(item.caller, item.kind, item.call_id) for item in field.passes] == [
        ("t.api:caller", PassKind.UNKNOWN, "C1")
    ]


# --- the service page ----------------------------------------------------------------------------


def test_analyze_writes_what_callers_pass_on_the_service_page(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from wm_doc.cli import app

    _server(tmp_path / "packages")
    output = tmp_path / "out"

    result = CliRunner().invoke(
        app, ["analyze", str(tmp_path / "packages"), "--output", str(output)]
    )

    assert result.exit_code == 0, result.output
    pages = {
        path.name: path.read_text(encoding="utf-8") for path in (output / "services").iterdir()
    }
    route = next(text for name, text in pages.items() if "route" in name)
    assert "What its callers pass (calls from analysed services):" in route
    assert "so on this call only D1.c1 (`ACTIVE`) can run" in route


def test_the_service_page_says_what_callers_pass(tmp_path: Path) -> None:
    analysis = _server(tmp_path)
    service = _by_name(analysis)[ROUTE]
    logic = compute_flow_logic(service)
    writes = compute_pipeline_writes(analysis.services)
    signatures = {item.identity.full_name: item.signature for item in analysis.services}
    lineage = compute_flow_lineage(service, logic, signatures, writes=writes)

    text = render_decisions_section(logic, lineage, None, inputs=_inputs(analysis))

    assert "What its callers pass (" in text
    assert (
        "`calls.api:fromActive` C1: set to `ACTIVE` in the input map of C1 `calls.api:route`"
    ) in text
    assert "so on this call only D1.c1 (`ACTIVE`) can run" in text
    assert "so on this call only D1.c3 (no other case matches) can run" in text
    assert "`calls.api:passThrough` C1: does not set it before the call" in text
    assert "C1 `ext.api:other` runs before the call and may change it" in text
    assert "Decision inputs:" in text and "`/status` (a declared input; tested by D1)" in text
