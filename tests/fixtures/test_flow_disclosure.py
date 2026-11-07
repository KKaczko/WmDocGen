"""Stage 5 of the conditional-flow work: FLOW labels and EXITs under the free-text policy.

Case labels keep their kind (`$null`, blank, a pattern, other text) when the policy withholds
their text, and label expressions keep the fields they refer to, so the control model stays
exact in every mode. EXIT labels and failure messages go through the policy with the secret
guard first; only the reserved scopes (`$flow`, `$parent`, `$loop`, `$iteration`) stay raw.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flowxml import FlowPackage, branch, case, exit_, invoke, loop, record, string

from wm_doc.config import ExtractionMode
from wm_doc.flow_logic import ConditionKind, Reach, compute_flow_logic
from wm_doc.ir import (
    ANALYSIS_SCHEMA_VERSION,
    CaseLabelKind,
    FlowNode,
    FlowNodeType,
    FlowService,
    TextDisclosure,
)
from wm_doc.pseudocode import render_pseudocode
from wm_doc.render.flow_markdown import condition_text, no_match_text

SERVICE = "orders.api:route"
SECRET_MESSAGE = "token=abc123 was rejected"
WITHHOLDING = [ExtractionMode.REDACT, ExtractionMode.OMIT]
EVERY_MODE = [ExtractionMode.INCLUDE, *WITHHOLDING]


def _service(root: Path, mode: ExtractionMode) -> tuple[FlowService, str]:
    pkg = FlowPackage(root / mode.value, "Orders")
    pkg.service(
        SERVICE,
        branch(
            case("$null", invoke("orders.api:missing")),
            case("ACTIVE", invoke("orders.api:active")),
            case("/^ARCH.*/", invoke("orders.api:archived")),
            case("", invoke("orders.api:blank")),
            switch="/request/status",
        ),
        branch(
            case('%request/kind% == "B2B"', invoke("orders.api:b2b")),
            case("$default", invoke("orders.api:other")),
            expressions=True,
        ),
        loop(
            branch(case("STOP", exit_("Each line")), switch="/lines/flag"),
            invoke("orders.api:line"),
            in_array="/lines",
            name="Each line",
        ),
        exit_("$flow", "FAILURE", SECRET_MESSAGE),
        inputs=[record("request", [string("status"), string("kind")])],
    )
    analysis = pkg.analyze(free_text=mode)
    return analysis.services[0], analysis.model_dump_json()


def _nodes(node: FlowNode | None, kind: FlowNodeType) -> list[FlowNode]:
    if node is None:
        return []
    found = [node] if node.type is kind else []
    for child in node.children:
        found += _nodes(child, kind)
    return found


def test_the_schema_is_analysis_v12() -> None:
    assert ANALYSIS_SCHEMA_VERSION == "analysis.v12"


# --- case labels -----------------------------------------------------------------------------


@pytest.mark.parametrize("mode", EVERY_MODE)
def test_case_kinds_survive_every_free_text_mode(tmp_path: Path, mode: ExtractionMode) -> None:
    service, _payload = _service(tmp_path, mode)

    cases = _nodes(service.flow_tree, FlowNodeType.BRANCH_CASE)

    assert [node.case_kind for node in cases] == [
        CaseLabelKind.NULL,
        CaseLabelKind.TEXT,
        CaseLabelKind.PATTERN,
        CaseLabelKind.BLANK,
        CaseLabelKind.TEXT,
        CaseLabelKind.DEFAULT,
        CaseLabelKind.TEXT,
    ]
    assert cases[4].condition_refs == ["/request/kind"]
    assert cases[1].condition_refs is None  # a switch label is not an expression


@pytest.mark.parametrize("mode", WITHHOLDING)
def test_withheld_labels_keep_their_kind_in_the_control_model(
    tmp_path: Path, mode: ExtractionMode
) -> None:
    service, payload = _service(tmp_path, mode)

    logic = compute_flow_logic(service)

    first = logic.decision("D1")
    assert [case.condition.kind for case in first.cases] == [
        ConditionKind.NULL,
        ConditionKind.VALUE,
        ConditionKind.PATTERN,
        ConditionKind.EMPTY,
    ]
    assert [case.condition.withheld for case in first.cases] == [False, True, True, False]
    assert [case.condition.text for case in first.cases] == ["$null", None, None, None]
    assert not first.missing_fails  # the $null case takes a missing switch
    assert "withheld label" not in no_match_text(first)
    assert condition_text(first, first.cases[1]) == "`/request/status` is a value (withheld)"
    expression_case = logic.decision("D2").cases[0]
    expression = expression_case.condition
    assert expression.kind is ConditionKind.EXPRESSION and expression.withheld
    assert [ref.text() for ref in expression.refs] == ["/request/kind"]
    assert expression_case.unreachable_rule is None  # withheld is not blank or $null (S8)
    assert logic.call("C5").reach is not Reach.UNREACHABLE
    for text in ("ACTIVE", "ARCH", "B2B"):
        assert text not in payload


def test_included_labels_read_as_before(tmp_path: Path) -> None:
    service, _payload = _service(tmp_path, ExtractionMode.INCLUDE)

    first = compute_flow_logic(service).decision("D1")

    assert [case.condition.text for case in first.cases] == ["$null", "ACTIVE", "/^ARCH.*/", None]
    assert not any(case.condition.withheld for case in first.cases)
    assert condition_text(first, first.cases[1]) == "`/request/status` is `ACTIVE`"


@pytest.mark.parametrize("mode", WITHHOLDING)
def test_the_prompt_never_shows_a_withheld_label_as_empty(
    tmp_path: Path, mode: ExtractionMode
) -> None:
    service, _payload = _service(tmp_path, mode)

    text = render_pseudocode(service, lambda _name: None)

    assert text.count('when "":') == 1  # only the blank label
    assert "when missing:" in text
    assert "when (value withheld):" in text
    assert "when (pattern withheld):" in text
    assert "when (expression withheld):" in text


# --- EXIT labels and failure messages ---------------------------------------------------------


@pytest.mark.parametrize("mode", EVERY_MODE)
def test_exit_labels_and_failure_messages_follow_the_policy(
    tmp_path: Path, mode: ExtractionMode
) -> None:
    service, payload = _service(tmp_path, mode)
    loop_node = _nodes(service.flow_tree, FlowNodeType.LOOP)[0]
    label_exit, flow_exit = _nodes(service.flow_tree, FlowNodeType.EXIT)

    disclosure = {
        ExtractionMode.INCLUDE: TextDisclosure.INCLUDED,
        ExtractionMode.REDACT: TextDisclosure.REDACTED,
        ExtractionMode.OMIT: TextDisclosure.OMITTED,
    }[mode]
    assert label_exit.exit_from is None
    assert label_exit.exit_label is not None and label_exit.exit_label.disclosure is disclosure
    assert label_exit.exit_target_id == loop_node.id  # resolved from the file in every mode
    assert flow_exit.exit_from == "$flow"
    assert flow_exit.failure_message is not None
    assert flow_exit.failure_message.disclosure is (
        TextDisclosure.OMITTED if mode is ExtractionMode.OMIT else TextDisclosure.BLOCKED_SECRET
    )
    for node in (label_exit, flow_exit):
        assert set(node.attributes) == {"SIGNAL"}  # FROM and FAILURE-MESSAGE never raw
    assert "abc123" not in payload
    if mode is not ExtractionMode.INCLUDE:
        assert "Each line" not in payload
    logic = compute_flow_logic(service)
    assert logic.exit("E1").target_id == loop_node.id


def test_the_prompt_shows_exit_labels_and_messages_only_as_the_policy_allows(
    tmp_path: Path,
) -> None:
    included, _payload = _service(tmp_path, ExtractionMode.INCLUDE)
    redacted, _payload = _service(tmp_path, ExtractionMode.REDACT)

    shown = render_pseudocode(included, lambda _name: None)
    hidden = render_pseudocode(redacted, lambda _name: None)

    assert 'EXIT "Each line" with success' in shown
    assert "EXIT the service with failure message (withheld)" in shown
    assert "abc123" not in shown
    assert "EXIT a labelled step (label withheld) with success" in hidden
    assert "Each line" not in hidden


def test_a_blank_failure_message_is_no_message(tmp_path: Path) -> None:
    pkg = FlowPackage(tmp_path, "Orders")
    pkg.service(SERVICE, exit_("$flow", "FAILURE", "  "))

    node = _nodes(pkg.analyze().services[0].flow_tree, FlowNodeType.EXIT)[0]

    assert node.failure_message is None
