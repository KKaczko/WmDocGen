"""Documents another service or the caller may share (assumption S39), and unnamed INVOKEs.

Linking a whole document shares it (S38). The lineage used to know only the links a service
makes itself, so a change made through a document linked elsewhere (by the caller, or by an
earlier called service) was missed, and a literal could wrongly be the only possible value:

    caller:  MAPSET /x/status = "A"; INVOKE setStatus; BRANCH /x/status
    setStatus: MAPSET /y/status = "B"       (/x and /y may be one document)

Now a change inside one document may change the field with the same path below any other
document; such changes are possible origins and keep calls "in between", so nothing is
concluded from the literal. An INVOKE without a SERVICE may change anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from flowxml import FlowPackage, branch, case, copy, invoke, loop, map_, set_

from wm_doc.flow_callers import compute_decision_inputs
from wm_doc.flow_lineage import FlowLineage, OriginKind, compute_flow_lineage
from wm_doc.flow_logic import FlowLogic, compute_flow_logic
from wm_doc.flow_scenarios import FlowScenarios, compute_flow_scenarios
from wm_doc.flow_semantics import RULES_BY_ID, RuleStatus
from wm_doc.flow_writes import PipelineWrites, compute_pipeline_writes
from wm_doc.ir import AnalysisResult
from wm_doc.render.flow_markdown import render_decisions_section

UNNAMED_INVOKE = '<INVOKE TIMEOUT="" VALIDATE-IN="$none" VALIDATE-OUT="$none">\n</INVOKE>'


@dataclass
class Subject:
    logic: FlowLogic
    lineage: FlowLineage
    scenarios: FlowScenarios

    def kinds(self) -> list[OriginKind]:
        return [self.lineage.origin(item).kind for item in self.lineage.variables[0].origins]


def _subject(analysis: AnalysisResult, name: str) -> Subject:
    service = next(item for item in analysis.services if item.identity.full_name == name)
    logic = compute_flow_logic(service)
    assert logic is not None
    signatures = {item.identity.full_name: item.signature for item in analysis.services}
    writes = compute_pipeline_writes(analysis.services)
    lineage = compute_flow_lineage(service, logic, signatures, writes=writes)
    assert lineage is not None
    scenarios = compute_flow_scenarios(service, logic, lineage, signatures, writes=writes)
    assert scenarios is not None
    return Subject(logic, lineage, scenarios)


# --- what a called service may change ------------------------------------------------------


@pytest.mark.parametrize(
    ("written", "tested", "may"),
    [
        (("y", "status"), ("x", "status"), True),  # /y and /x may be one document
        (("y", "order", "status"), ("x", "status"), True),  # /y/order may be /x
        (("y", "sub"), ("x", "sub", "status"), True),  # replacing /y/sub replaces /x/sub
        (("y", "z", "t"), ("x", "t"), True),  # /y/z may be /x
        (("y", "t", "u"), ("x", "t"), True),  # a change inside /y/t is one inside /x/t
        (("a", "b", "t"), ("x", "y", "t"), True),  # /a/b may be /x/y
        (("y", "other"), ("x", "status"), False),  # another field
        (("status",), ("x", "status"), False),  # a pipeline field, not inside a document
        (("y", "x"), ("x", "status"), False),  # `x` inside /y is not the pipeline's /x
        (("x", "status"), ("status",), False),  # a first-level field is never shared
    ],
)
def test_a_summary_may_change_the_same_field_of_another_document(
    written: tuple[str, ...], tested: tuple[str, ...], may: bool
) -> None:
    assert PipelineWrites(frozenset({written}), False).may_change(tested) is may


def test_a_called_service_writing_another_document_keeps_the_call_in_between(
    tmp_path: Path,
) -> None:
    pkg = FlowPackage(tmp_path, "Shared")
    pkg.service("s.api:setStatus", map_(set_("/y/status", "B")))
    pkg.service("s.api:setOther", map_(set_("/y/other", "B")))
    for name, helper in (("s.api:decides", "s.api:setStatus"), ("s.api:other", "s.api:setOther")):
        pkg.service(
            name,
            map_(set_("/x/status", "A")),
            invoke(helper),
            branch(case("A", invoke("s.api:a")), case("B", invoke("s.api:b")), switch="/x/status"),
        )
    analysis = pkg.analyze()

    (variable,) = _subject(analysis, "s.api:decides").lineage.variables
    assert variable.calls_in_between == ("C1",)
    assert not variable.unique
    # A helper that writes a field of another name still proves the call harmless.
    (other,) = _subject(analysis, "s.api:other").lineage.variables
    assert other.calls_in_between == ()
    assert other.unique


# --- documents the caller may have linked ----------------------------------------------------


def test_a_change_inside_another_document_is_a_possible_origin(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Shared")
    pkg.service(
        "s.api:decides",
        map_(set_("/x/status", "A")),
        map_(set_("/y/status", "B")),  # the caller may have passed /x and /y linked
        branch(case("A", invoke("s.api:a")), case("B", invoke("s.api:b")), switch="/x/status"),
    )

    subject = _subject(pkg.analyze(), "s.api:decides")

    (variable,) = subject.lineage.variables
    assert subject.kinds() == [OriginKind.SET, OriginKind.SHARED]
    shared = subject.lineage.origin(variable.origins[1])
    assert shared.rules == ("S39",)
    assert shared.written_path is not None and shared.written_path.text() == "/y/status"
    assert not variable.unique
    text = render_decisions_section(subject.logic, subject.lineage, subject.scenarios)
    assert "a document the caller or a called service may share with this one" in text
    assert "assumption S39" in text


def test_nothing_is_ruled_out_when_another_document_may_change_the_field(
    tmp_path: Path,
) -> None:
    pkg = FlowPackage(tmp_path, "Shared")
    pkg.service(
        "s.api:decides",
        branch(case("K", map_(set_("/x/t", "AB"))), switch="/k"),
        map_(set_("/y/t", "X")),
        branch(case("AB", invoke("s.api:ab")), case("X", invoke("s.api:x")), switch="/x/t"),
    )

    scenarios = _subject(pkg.analyze(), "s.api:decides").scenarios

    table = next(item for item in scenarios.tables if item.decision_ids == ("D1", "D2"))
    assert table.ruled_out == ()


def test_a_document_linked_here_is_still_reported_as_linked(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Shared")
    pkg.service(
        "s.api:decides",
        map_(copy("/x", "/y")),  # linked in this service (S38)
        map_(set_("/y/status", "B")),
        branch(case("B", invoke("s.api:b")), switch="/x/status"),
    )

    kinds = _subject(pkg.analyze(), "s.api:decides").kinds()

    assert OriginKind.LINKED in kinds and OriginKind.SHARED not in kinds


@pytest.mark.parametrize("linked_here", [False, True])
def test_a_loop_out_array_inside_a_document_may_change_another_one(
    tmp_path: Path, linked_here: bool
) -> None:
    pkg = FlowPackage(tmp_path, "Shared")
    pkg.service(
        "s.api:decides",
        *([map_(copy("/x", "/y"))] if linked_here else []),
        map_(set_("/y/t", "A")),
        loop(invoke("s.api:each"), in_array="/arr", out_array="/x/t"),
        branch(case("A", invoke("s.api:a")), case("B", invoke("s.api:b")), switch="/y/t"),
    )

    subject = _subject(pkg.analyze(), "s.api:decides")

    expected = OriginKind.LINKED if linked_here else OriginKind.SHARED
    assert expected in subject.kinds()
    assert not subject.lineage.variables[0].unique


def test_a_caller_literal_that_another_document_may_change_decides_nothing(
    tmp_path: Path,
) -> None:
    pkg = FlowPackage(tmp_path, "Shared")
    pkg.service(
        "s.api:route",
        branch(case("A", invoke("s.api:a")), case("B", invoke("s.api:b")), switch="/x/status"),
    )
    pkg.service(
        "s.api:caller",
        map_(set_("/x/status", "A")),
        map_(set_("/y/status", "B")),
        invoke("s.api:route"),
    )
    pkg.service(
        "s.api:plain",
        map_(set_("/x/status", "A")),
        map_(set_("/y/other", "B")),
        invoke("s.api:route"),
    )
    analysis = pkg.analyze()
    service = next(item for item in analysis.services if item.identity.full_name == "s.api:route")
    logic = compute_flow_logic(service)
    assert logic is not None
    signatures = {item.identity.full_name: item.signature for item in analysis.services}
    writes = compute_pipeline_writes(analysis.services)
    lineage = compute_flow_lineage(service, logic, signatures, writes=writes)
    callers = [item for item in analysis.services if item.identity.full_name != "s.api:route"]

    (field,) = compute_decision_inputs(
        service, logic, lineage, callers=callers, signatures=signatures, writes=writes
    )

    cases = {item.caller: item.cases for item in field.passes}
    assert cases["s.api:caller"] is None  # /y/status may be /x/status (S39)
    assert cases["s.api:plain"] is not None  # another field name: the literal decides


def test_the_rule_is_an_assumption_to_check_on_integration_server() -> None:
    rule = RULES_BY_ID["S39"]
    assert rule.status is RuleStatus.ASSUMED
    assert rule.checks == ("V35",)


# --- an INVOKE without a SERVICE --------------------------------------------------------------


def test_an_invoke_without_a_service_may_change_anything(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Unnamed")
    pkg.service(
        "u.api:decides",
        map_(set_("/s", "A")),
        UNNAMED_INVOKE,
        branch(case("A", invoke("u.api:a")), case("B", invoke("u.api:b")), switch="/s"),
    )
    pkg.service("u.api:caller", invoke("u.api:decides"))
    analysis = pkg.analyze()

    writes = compute_pipeline_writes(analysis.services)
    assert writes["u.api:decides"].unknown
    assert writes["u.api:caller"].unknown
    subject = _subject(analysis, "u.api:decides")
    assert subject.kinds() == [OriginKind.SET, OriginKind.UNKNOWN]
    assert not subject.lineage.variables[0].unique
    text = render_decisions_section(subject.logic, subject.lineage, subject.scenarios)
    assert "an INVOKE that names no service" in text
