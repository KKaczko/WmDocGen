"""The test FLOW builder writes services the analyser reads like Designer output."""

from __future__ import annotations

from pathlib import Path

import pytest
from flowxml import (
    FlowPackage,
    branch,
    case,
    copy,
    drop,
    exit_,
    invoke,
    loop,
    map_,
    record,
    repeat,
    seq,
    set_,
    string,
    transform,
    try_catch,
    typed,
)

from wm_doc.ir import FlowNode, FlowNodeType, FlowService


def _nodes(node: FlowNode | None, kind: FlowNodeType) -> list[FlowNode]:
    if node is None:
        return []
    found = [node] if node.type is kind else []
    for child in node.children:
        found.extend(_nodes(child, kind))
    return found


def _case_of_call(service: FlowService) -> dict[str, str | None]:
    """Call target -> label of the innermost case it sits in."""
    labels = {
        node.id: node.label.value if node.label else None
        for node in _nodes(service.flow_tree, FlowNodeType.BRANCH_CASE)
    }
    result: dict[str, str | None] = {}
    for call in service.call_occurrences:
        enclosing = [item for item in call.parent_flow_path if item in labels]
        result[call.target] = labels[enclosing[-1]] if enclosing else None
    return result


def process_order(tmp_path: Path, *, typed_switch: bool = False) -> FlowPackage:
    pkg = FlowPackage(tmp_path / "packages", "Orders")
    pkg.service(
        "orders.api:processOrder",
        branch(
            case(
                "ACTIVE",
                invoke(
                    "systemA:validateOrder",
                    outputs=[copy("/result/status", "/validationStatus")],
                ),
            ),
            case("FINALIZED", invoke("systemB:finalizeOrder")),
            switch="/request/status",
            typed_switch=typed_switch,
        ),
        branch(
            case("OK", invoke("systemC:activateOrder")),
            case("ERROR", invoke("common:handleError")),
            switch="/validationStatus",
        ),
        inputs=[record("request", [string("status")])],
    )
    return pkg


def test_typed_adds_designer_suffixes_once() -> None:
    assert typed("/request/status") == "/request;2;0/status;1;0"
    assert typed("/orders") == "/orders;1;0"
    assert typed("/a;2;0/b;1;0") == "/a;2;0/b;1;0"
    assert typed("%x% == 1") == "%x% == 1"


@pytest.mark.parametrize(
    ("typed_switch", "expected"),
    [(False, "/request/status"), (True, "/request;2;0/status;1;0")],
)
def test_process_order_example_analyses_without_findings(
    tmp_path: Path, typed_switch: bool, expected: str
) -> None:
    service = process_order(tmp_path, typed_switch=typed_switch).analyze().services[0]

    assert service.identity.full_name == "orders.api:processOrder"
    assert service.findings == []
    assert [field.name for field in service.signature.inputs] == ["request"]
    branches = _nodes(service.flow_tree, FlowNodeType.BRANCH)
    assert [node.switch for node in branches] == [expected, "/validationStatus"]
    assert _case_of_call(service) == {
        "systemA:validateOrder": "ACTIVE",
        "systemB:finalizeOrder": "FINALIZED",
        "systemC:activateOrder": "OK",
        "common:handleError": "ERROR",
    }
    output_map = next(m for m in service.flow_maps if m.mode == "OUTPUT")
    assert output_map.parent_call_occurrence_id == service.call_occurrences[0].id


def test_unwrapped_cases_put_the_label_on_the_step_like_designer(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path / "packages", "Keys")
    pkg.service(
        "keys.api:verify",
        branch(
            case("1", map_(set_("/verified", "true")), wrap=False),
            case("$default", invoke("keys.api:reject"), wrap=False),
            switch="/verified",
        ),
    )

    service = pkg.analyze().services[0]

    assert service.findings == []
    cases = _nodes(service.flow_tree, FlowNodeType.BRANCH_CASE)
    assert [node.children[0].type for node in cases] == [FlowNodeType.MAP, FlowNodeType.INVOKE]
    assert [node.label.value if node.label else None for node in cases] == ["1", "$default"]
    assert cases[1].is_default_case is True
    assert _case_of_call(service) == {"keys.api:reject": "$default"}
    with pytest.raises(ValueError):
        case("x", map_(), map_(), wrap=False)


def test_package_and_service_names_are_checked(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        FlowPackage(tmp_path, "WmSkipped")
    with pytest.raises(ValueError):
        FlowPackage(tmp_path, "Pkg").service("noColon")


def test_every_builder_step_is_understood(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path / "packages", "Shapes")
    pkg.service(
        "shapes.all:everyStep",
        map_(
            set_("/mode", "fast"),
            set_("/maybe", "x", overwrite=False, variables=True),
            copy("/request/id", "/id"),
            transform("pub.string:toUpper", [copy("/id", "/inString")], [copy("/value", "/up")]),
            drop("/request;2;0"),
            name="Prepare",
        ),
        try_catch(
            [
                loop(
                    branch(case("$null", exit_("$loop")), switch="/items/status"), in_array="/items"
                )
            ],
            [invoke("pub.flow:getLastError")],
            [map_(set_("/done", "yes"))],
        ),
        repeat(invoke("other.api:call"), count="2"),
        seq(invoke("other.api:first"), invoke("other.api:second"), exit_on="DONE"),
        branch(
            case('%mode% == "fast"', exit_("$flow", "FAILURE", "stopped")),
            case("$default", map_(set_("/slow", "yes"))),
            expressions=True,
        ),
        invoke("other.api:skipped", disabled=True),
    )

    service = pkg.analyze().services[0]

    assert service.findings == []
    assert service.disabled_steps == 1
    counts = service.metrics.flow_node_counts
    for kind in ("SEQUENCE", "BRANCH", "BRANCH_CASE", "LOOP", "REPEAT", "MAP", "INVOKE", "EXIT"):
        assert counts.get(kind), kind
    forms = [node.form for node in _nodes(service.flow_tree, FlowNodeType.SEQUENCE)]
    assert {"TRY", "CATCH", "FINALLY"} <= set(forms)
    exits = _nodes(service.flow_tree, FlowNodeType.EXIT)
    assert [(node.exit_from, node.signal, node.failure_message) for node in exits] == [
        ("$loop", "SUCCESS", ""),
        ("$flow", "FAILURE", "stopped"),
    ]
    expression_branch = _nodes(service.flow_tree, FlowNodeType.BRANCH)[-1]
    assert expression_branch.evaluate_labels is True
    first_map = service.mapping_operations
    sets = [op for op in first_map if op.operation_type.value == "SET"]
    assert sets[1].technical_attrs["OVERWRITE"] == "false"
    assert sets[1].technical_attrs["VARIABLES"] == "true"
    assert {op.operation_type.value for op in first_map} == {"SET", "COPY", "DELETE"}
    assert [binding.direction.value for binding in service.transformer_bindings] == [
        "INTO_TRANSFORMER",
        "FROM_TRANSFORMER",
    ]
