"""The conditional flow of a FLOW service for the explorer (`flows/<id>.json`).

Python owns everything here: the control model (`flow_logic`), where decision fields come
from (`flow_lineage`) and the scenarios (`flow_scenarios`) are computed as for the service
pages and turned into display text with the same wording (`render.flow_markdown`). The app
only shows the result.

What is never exported: mapping literals (a SET origin reads "set to a literal (literal, not
exported)", ruled-out scenarios never name the literal), EXIT failure messages and designer
comments. Branch condition values (case labels) are shown, as on the pages, unless the build
excludes them: the facts are then computed from the real labels and only shown with the
values withheld, and steps named after a case label lose that name. Every text that may hold
a label passes the disclosure scan (`TextGuard`).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace

from pydantic import BaseModel

from wm_doc.call_targets import TargetStatus
from wm_doc.explorer.contract import (
    CallReach,
    ConditionValues,
    FlowCall,
    FlowCase,
    FlowDecision,
    FlowField,
    FlowOrigin,
    FlowRef,
    FlowScenarioRow,
    FlowScenarioTable,
    FlowStep,
    FlowStepKind,
    FlowView,
    OriginBasis,
    Segment,
    SourceRef,
)
from wm_doc.explorer.contract import Certainty as CertaintyLevel
from wm_doc.explorer.contract import Feasibility as FeasibilityLevel
from wm_doc.explorer.text import TextGuard
from wm_doc.flow_lineage import (
    FlowLineage,
    Origin,
    OriginKind,
    VariableOrigins,
    compute_flow_lineage,
)
from wm_doc.flow_logic import (
    CaseCondition,
    Certainty,
    ConditionKind,
    Decision,
    DecisionCase,
    FlowLogic,
    Reach,
    code_span,
    compute_flow_logic,
    sort_rules,
    step_form,
)
from wm_doc.flow_paths import path_ref
from wm_doc.flow_scenarios import (
    Feasibility,
    FlowScenarios,
    Scenario,
    ScenarioTable,
    compute_flow_scenarios,
)
from wm_doc.flow_semantics import assumption_label, rule_label
from wm_doc.ir import CallType, FlowNode, FlowNodeType, FlowService, ServiceSignature
from wm_doc.ir import SourceReference as IrSourceReference
from wm_doc.render.flow_markdown import (
    MAX_CALL_ROWS,
    MAX_CASE_CALLS,
    MAX_CHAIN,
    MAX_COPY_DEPTH_SHOWN,
    MAX_DECISIONS_SHOWN,
    MAX_IDS,
    MAX_LIST_ROWS,
    MAX_ORIGIN_LINES,
    MAX_ORIGINS_SHOWN,
    MAX_RULED_SHOWN,
    MAX_SCENARIOS,
    MAX_SOURCE_ORIGINS,
    MAX_VARIABLES_SHOWN,
    UNFOLLOWED_TEXT,
    call_ref,
    calls_text,
    condition_text,
    decision_title,
    exit_lines,
    exit_ref,
    exit_text,
    guard_text,
    no_match_text,
    not_followed,
    note_text,
    origin_assumptions,
    origin_certainty,
    origin_text,
    outcomes_text,
    ruled_text,
    runs_when,
    scenario_call,
    scenario_end,
    unreachable_lines,
)

MAX_OUTLINE_STEPS = 1_500
MAX_FLOW_DECISIONS = MAX_DECISIONS_SHOWN
MAX_FLOW_CALLS = MAX_CALL_ROWS
MAX_FLOW_TEXT = 1_200

_CERTAINTY: dict[Certainty, CertaintyLevel] = {
    Certainty.OBSERVED: "observed",
    Certainty.DERIVED: "derived",
    Certainty.POSSIBLE: "possible",
    Certainty.UNKNOWN: "unknown",
}
_FEASIBILITY: dict[Feasibility, FeasibilityLevel] = {
    Feasibility.POSSIBLE: "possible",
    Feasibility.CONDITIONAL: "conditional",
    Feasibility.UNRESOLVED: "unresolved",
}
_REACH: dict[Reach, CallReach] = {
    Reach.NORMAL: "normal",
    Reach.CONDITIONAL: "conditional",
    Reach.FAILURE_PATH: "failure-path",
    Reach.UNREACHABLE: "unreachable",
}
_BASIS: dict[OriginKind, OriginBasis] = {
    OriginKind.SET: "flow-xml",
    OriginKind.COPY: "flow-xml",
    OriginKind.TRANSFORMER: "flow-xml",
    OriginKind.DROPPED: "flow-xml",
    OriginKind.PARTIAL: "flow-xml",
    OriginKind.COLLECTED: "flow-xml",
    OriginKind.CALL_RESPONSE: "callee-signature",
    OriginKind.CLEARED: "is-rule",
    OriginKind.RESTORED: "is-rule",
    OriginKind.LINKED: "is-rule",
    OriginKind.SERVICE_INPUT: "service-signature",
    OriginKind.CALLER: "caller-pipeline",
    OriginKind.UNKNOWN: "limit",
}
_FORM_KINDS: dict[str, FlowStepKind] = {"TRY": "try", "CATCH": "catch", "FINALLY": "finally"}
# Step names as flow_logic writes them, for steps whose label is a case label.
_STEP_KINDS = {
    FlowNodeType.SEQUENCE: "SEQUENCE",
    FlowNodeType.BRANCH: "BRANCH",
    FlowNodeType.BRANCH_CASE: "case",
    FlowNodeType.LOOP: "LOOP",
    FlowNodeType.REPEAT: "REPEAT",
    FlowNodeType.MAP: "MAP",
    FlowNodeType.INVOKE: "INVOKE",
    FlowNodeType.MAPINVOKE: "transformer",
    FlowNodeType.EXIT: "EXIT",
}
# Kinds for steps the control model does not list (a fallback; it lists every BRANCH, case,
# call and EXIT it analyses).
_FALLBACK_KINDS: dict[FlowNodeType, FlowStepKind] = {
    FlowNodeType.BRANCH: "branch",
    FlowNodeType.BRANCH_CASE: "case",
    FlowNodeType.INVOKE: "call",
    FlowNodeType.MAPINVOKE: "transformer",
    FlowNodeType.EXIT: "exit",
    FlowNodeType.MAP: "map",
}
MAX_FLOW_CASES = 40  # cases per decision, as in a description file's facts block
# Bytes of JSON each part of a flow file may use, so one file stays well under 200 KB however
# large the service is; what does not fit is counted as "and N more".
OUTLINE_BYTES = 70_000
DECISION_BYTES = 60_000
CALL_BYTES = 25_000
SCENARIO_BYTES = 20_000
LIST_BYTES = 10_000


class _Bytes:
    """A byte budget: items are taken in order until the next one does not fit."""

    def __init__(self, limit: int) -> None:
        self.left = limit

    def take(self, item: BaseModel | list[Segment]) -> bool:
        if isinstance(item, BaseModel):
            cost = len(item.model_dump_json(by_alias=True))
        else:
            cost = sum(len(segment.model_dump_json(by_alias=True)) for segment in item) + 4
        if cost > self.left:
            self.left = 0
            return False
        self.left -= cost
        return True


def _fit[T: BaseModel | list[Segment]](items: Iterable[T], budget: _Bytes) -> tuple[list[T], int]:
    """The items that fit the budget, in order, and how many did not."""
    kept: list[T] = []
    hidden = 0
    for item in items:
        if hidden or not budget.take(item):
            hidden += 1
        else:
            kept.append(item)
    return kept, hidden


def flow_view(
    service: FlowService,
    service_id: str,
    refs: Mapping[str, str],
    guard: TextGuard,
    signatures: Mapping[str, ServiceSignature],
    *,
    condition_values: ConditionValues,
) -> tuple[FlowRef, FlowView] | None:
    """The flow file of a service with decisions, EXITs or TRY/CATCH; None otherwise."""
    logic = compute_flow_logic(service)
    if logic is None or not logic.significant or service.flow_tree is None:
        return None
    lineage = compute_flow_lineage(service, logic, signatures)
    scenarios = compute_flow_scenarios(service, logic, lineage, signatures)
    shown = logic if condition_values == "included" else _without_condition_values(logic, service)
    text = _Text(guard, refs)
    outline = _Outline(shown, refs, text)
    steps = outline.steps(service.flow_tree.children)
    origin_limits = lineage.limits if lineage is not None else ()
    limits = [*logic.limits, *(f"Origin limit: {item}" for item in origin_limits)]
    budget = _Bytes(DECISION_BYTES)
    decisions: list[FlowDecision] = []
    for decision in shown.decisions[:MAX_FLOW_DECISIONS]:
        item = _decision(shown, lineage, decision, text, budget)
        if item is None:
            break
        decisions.append(item)
    calls, calls_hidden = _fit(
        (_call(shown, call.id, refs, text) for call in shown.calls[:MAX_FLOW_CALLS]),
        _Bytes(CALL_BYTES),
    )
    lists = _Bytes(LIST_BYTES)
    exits, exits_hidden = _fit((text.segments(line) for line in exit_lines(shown)), lists)
    never_run, never_hidden = _fit(
        (text.segments(line) for line in unreachable_lines(shown)), lists
    )
    view = FlowView(
        service_id=service_id,
        outline=steps,
        outline_hidden=outline.hidden,
        decisions=decisions,
        decisions_hidden=len(shown.decisions) - len(decisions),
        calls=calls,
        calls_hidden=calls_hidden + max(0, len(shown.calls) - MAX_FLOW_CALLS),
        exits=exits,
        exits_hidden=exits_hidden + max(0, len(shown.exits) - MAX_LIST_ROWS),
        never_run=never_run,
        never_run_hidden=never_hidden + max(0, len(shown.unreachable) - MAX_LIST_ROWS),
        scenarios=_scenario_tables(shown, scenarios, text, _Bytes(SCENARIO_BYTES)),
        scenario_notes=_scenario_notes(scenarios, text),
        limits=[text.segments(line) for line in limits],
    )
    ref = FlowRef(decisions=len(logic.decisions), calls=len(logic.calls), exits=len(logic.exits))
    return ref, view


class _Text:
    """Display text: code spans become segments (a service name links to its page)."""

    def __init__(self, guard: TextGuard, refs: Mapping[str, str]) -> None:
        self.guard = guard
        self.refs = refs

    def segments(self, text: str) -> list[Segment]:
        # Labels are designer text, so every line is disclosure-scanned as a whole.
        return self.guard.segments(text, self.refs, prose=True, limit=MAX_FLOW_TEXT)


# --- condition values left out ------------------------------------------------------------------


def _without_condition_values(logic: FlowLogic, service: FlowService) -> FlowLogic:
    """The same logic with every case label shown as withheld, for display only."""
    decisions = tuple(
        replace(
            decision,
            cases=tuple(
                replace(case, condition=_hidden(case.condition)) for case in decision.cases
            ),
        )
        for decision in logic.decisions
    )
    named = _named_after_labels(service.flow_tree)
    step_text = {
        node_id: _unlabelled(named[node_id]) if node_id in named else text
        for node_id, text in logic.step_text.items()
    }
    return replace(logic, decisions=decisions, step_text=step_text)


def _hidden(condition: CaseCondition) -> CaseCondition:
    if condition.withheld or condition.kind not in (
        ConditionKind.VALUE,
        ConditionKind.PATTERN,
        ConditionKind.EXPRESSION,
    ):
        return condition
    if condition.kind is ConditionKind.EXPRESSION and (condition.text or "").strip() in (
        "",
        "$null",
    ):
        return condition  # keywords, not values
    return replace(condition, text=None, withheld=True)


def _named_after_labels(root: FlowNode | None) -> dict[str, FlowNode]:
    """Case nodes and the steps that carry their label: in Designer the step a BRANCH runs is
    named after its case, so the parser gives a case's direct children the same label."""
    found: dict[str, FlowNode] = {}
    stack = [root] if root is not None else []
    while stack:
        node = stack.pop()
        if node.type is FlowNodeType.BRANCH_CASE:
            found[node.id] = node
            found.update((child.id, child) for child in node.children)
        stack.extend(node.children)
    return found


def _unlabelled(node: FlowNode) -> str:
    """How a reader finds the step without its label, written from the step itself."""
    kind = _STEP_KINDS.get(node.type, "step")
    form = step_form(node)
    if form is not None:
        kind = f"{form} block"
    line = f" (line {node.source.line})" if node.source.line else ""
    withheld = " (label withheld)" if node.label is not None else ""
    return f"the {kind}{line}{withheld}"


# --- the outline ---------------------------------------------------------------------------------


class _Outline:
    def __init__(self, logic: FlowLogic, refs: Mapping[str, str], text: _Text) -> None:
        self.logic = logic
        self.refs = refs
        self.text = text
        self.left = MAX_OUTLINE_STEPS
        self.bytes = _Bytes(OUTLINE_BYTES)
        self.hidden = 0
        self.decisions = {item.node_id: item for item in logic.decisions}
        self.cases = {case.node_id: (item, case) for item in logic.decisions for case in item.cases}
        self.calls = {item.node_id: item for item in logic.calls}
        self.exits = {item.node_id: item for item in logic.exits}

    def steps(self, nodes: Iterable[FlowNode], under_case: bool = False) -> list[FlowStep]:
        found: list[FlowStep] = []
        for node in nodes:
            found += self.step(node, under_case)
        return found

    def step(self, node: FlowNode, under_case: bool) -> list[FlowStep]:
        if self._flattened(node, under_case):
            return self.steps(node.children)
        if self.left <= 0:
            self.hidden += self._count(node, under_case)
            return []
        kind, ref, text, target_id, never = self._describe(node)
        step = FlowStep(
            kind=kind, ref=ref, text=self.text.segments(text), target_id=target_id, never=never
        )
        if not self.bytes.take(step):
            self.left = 0  # the outline is full: count this step and everything after it
            self.hidden += self._count(node, under_case)
            return []
        self.left -= 1
        nested, nested_under_case = _shown_children(node)
        return [step.model_copy(update={"children": self.steps(nested, nested_under_case)})]

    def _count(self, node: FlowNode, under_case: bool) -> int:
        """How many outline steps `node` would have given, walked as `step` walks."""
        if self._flattened(node, under_case):
            return sum(self._count(child, False) for child in node.children)
        nested, nested_under_case = _shown_children(node)
        return 1 + sum(self._count(child, nested_under_case) for child in nested)

    def _flattened(self, node: FlowNode, under_case: bool) -> bool:
        """A plain SEQUENCE (no form, EXIT-ON FAILURE) adds nothing a reader needs."""
        if node.type is not FlowNodeType.SEQUENCE or step_form(node) is not None:
            return False
        if (node.exit_on or "FAILURE").strip().upper() != "FAILURE":
            return False
        return under_case or node.label is None

    def _describe(self, node: FlowNode) -> tuple[FlowStepKind, str | None, str, str | None, bool]:
        logic = self.logic
        step = _short(logic.step_text.get(node.id, node.type.value))
        if node.type is FlowNodeType.BRANCH and node.id in self.decisions:
            decision = self.decisions[node.id]
            return "branch", decision.id, _untitled(decision), None, False
        if node.type is FlowNodeType.BRANCH_CASE and node.id in self.cases:
            decision, case = self.cases[node.id]
            never = case.unreachable_rule is not None
            return "case", case.id, condition_text(decision, case), None, never
        if node.type in (FlowNodeType.INVOKE, FlowNodeType.MAPINVOKE) and node.id in self.calls:
            call = self.calls[node.id]
            kind: FlowStepKind = "transformer" if call.call_type is CallType.MAPINVOKE else "call"
            target_id = (
                self.refs.get(call.target) if call.target_status is TargetStatus.RESOLVED else None
            )
            never = call.reach is Reach.UNREACHABLE
            return kind, call.id, code_span(call.target), target_id, never
        if node.type is FlowNodeType.EXIT and node.id in self.exits:
            item = self.exits[node.id]
            return "exit", item.id, exit_text(logic, item).removeprefix(f"{item.id} "), None, False
        if node.type is FlowNodeType.SEQUENCE:
            form = step_form(node)
            if form is not None:
                return _FORM_KINDS[form], None, step, None, False
            exit_on = (node.exit_on or "FAILURE").strip().upper()
            if exit_on == "SUCCESS":
                step += ", stops at the first child that succeeds"
            elif exit_on == "DONE":
                step += ", runs every child even after one fails"
            return "sequence", None, step, None, False
        if node.type is FlowNodeType.LOOP:
            array = path_ref(node.in_array)
            over = f", over {code_span(array.text())}" if array is not None else ""
            return "loop", None, step + over, None, False
        if node.type is FlowNodeType.REPEAT:
            return "repeat", None, step, None, False
        return _FALLBACK_KINDS.get(node.type, "sequence"), None, step, None, False


def _shown_children(node: FlowNode) -> tuple[list[FlowNode], bool]:
    """The children an outline step shows, and whether they are the steps of a case."""
    if node.type is FlowNodeType.BRANCH_CASE:
        return list(node.children), True
    if node.type in (FlowNodeType.MAP, FlowNodeType.INVOKE):
        return _transformers(node), False
    if node.type in (FlowNodeType.MAPINVOKE, FlowNodeType.EXIT):
        return [], False
    return list(node.children), False


def _transformers(node: FlowNode) -> list[FlowNode]:
    """The transformers of a MAP, or of the maps of an INVOKE."""
    found: list[FlowNode] = []
    for child in node.children:
        if child.type is FlowNodeType.MAPINVOKE:
            found.append(child)
        elif child.type is FlowNodeType.MAP:
            found += _transformers(child)
    return found


def _short(text: str) -> str:
    """'the SEQUENCE `x` (line 3)' becomes 'SEQUENCE `x` (line 3)'."""
    return text.removeprefix("the ")


def _untitled(decision: Decision) -> str:
    return decision_title(decision).removeprefix(f"{decision.id}: ")


# --- decisions -----------------------------------------------------------------------------------


def _decision(
    logic: FlowLogic,
    lineage: FlowLineage | None,
    decision: Decision,
    text: _Text,
    budget: _Bytes,
) -> FlowDecision | None:
    """A decision card, its cases and fields within `budget`; None when even its head does
    not fit (it and the decisions after it are then counted as not shown)."""
    variables = lineage.for_decision(decision.id) if lineage is not None else ()
    unfollowed = lineage.unfollowed.get(decision.id, ()) if lineage is not None else ()
    head = FlowDecision(
        id=decision.id,
        heading=text.segments(_untitled(decision)),
        evaluated_when=(
            text.segments(guard_text(logic, decision.guard)) if decision.guard.terms else None
        ),
        in_loop=decision.loop_id is not None,
        notes=[text.segments(note_text(note)) for note in decision.notes],
        cases=[],
        cases_hidden=0,
        no_match=text.segments(no_match_text(decision)) if decision.falls_through else None,
        fields=[],
        fields_hidden=0,
        unfollowed=[text.segments(UNFOLLOWED_TEXT.get(reason, reason)) for reason in unfollowed],
    )
    if not budget.take(head):
        return None
    cases, cases_hidden = _fit(
        (_case(logic, decision, case, text) for case in decision.cases[:MAX_FLOW_CASES]), budget
    )
    fields, fields_hidden = _fit(
        (
            _field(logic, lineage, item, text)
            for item in variables[:MAX_VARIABLES_SHOWN]
            if lineage is not None
        ),
        budget,
    )
    return head.model_copy(
        update={
            "cases": cases,
            "cases_hidden": cases_hidden + max(0, len(decision.cases) - MAX_FLOW_CASES),
            "fields": fields,
            "fields_hidden": fields_hidden + max(0, len(variables) - MAX_VARIABLES_SHOWN),
        }
    )


def _case(logic: FlowLogic, decision: Decision, case: DecisionCase, text: _Text) -> FlowCase:
    calls = [call_ref(logic, call_id) for call_id in case.call_ids[:MAX_CASE_CALLS]]
    if len(case.call_ids) > MAX_CASE_CALLS:
        calls.append(f"and {len(case.call_ids) - MAX_CASE_CALLS} more")
    ends = [exit_ref(logic, exit_id) for exit_id in case.ends_with[:MAX_IDS]]
    if len(case.ends_with) > MAX_IDS:
        ends.append(f"and {len(case.ends_with) - MAX_IDS} more")
    notes = []
    if case.unreachable_rule:
        notes.append(f"never runs ({rule_label([case.unreachable_rule])})")
    label = assumption_label(case.rules)
    if label:
        notes.append(label)
    return FlowCase(
        id=case.id,
        condition=text.segments(condition_text(decision, case)),
        calls=text.segments(", ".join(calls)),
        ends=text.segments(", ".join(ends)),
        notes=text.segments("; ".join(notes)),
        never=case.unreachable_rule is not None,
    )


def _field(
    logic: FlowLogic, lineage: FlowLineage, variable: VariableOrigins, text: _Text
) -> FlowField:
    path = variable.path.text()
    blocked = not_followed(variable)
    if blocked is not None:
        return FlowField(
            path=path, summary=text.segments(blocked), origins=[], origins_hidden=0, notes=[]
        )
    origins = [lineage.origin(origin_id) for origin_id in variable.origins]
    if variable.unique:
        summary = "Comes from:"
    elif len(origins) == 1 and origins[0].kind is OriginKind.CALLER:
        summary = (
            "Not set by this service before this decision; present only if the caller supplies it."
        )
    else:
        summary = "May come from any of:"
    chips: list[FlowOrigin] = []
    budget = [MAX_ORIGIN_LINES]
    expanded: set[str] = set()
    for origin in origins[:MAX_ORIGINS_SHOWN]:
        chips.append(_origin(logic, origin, text))
        chips += _sources(logic, lineage, origin, 1, expanded, budget, text)
    notes: list[list[Segment]] = []
    if variable.loop_path is not None:
        notes.append(
            text.segments(
                f"Inside the LOOP over {code_span(variable.loop_path.text())}, that path names "
                "the current element (S22)."
            )
        )
    if "list_element" in variable.notes:
        notes.append(
            text.segments(
                "The decision tests one list element; the origins are those of the whole field, "
                "so none of them is certain."
            )
        )
    if variable.calls_in_between:
        notes.append(
            text.segments(
                "Calls that run before the decision may also change it, because a called "
                "service shares the pipeline (S16): "
                f"{calls_text(logic, variable.calls_in_between, variable.more_calls_in_between)}."
            )
        )
    if variable.depends_on_calls:
        notes.append(
            text.segments(
                "It may carry what these calls return: "
                f"{calls_text(logic, variable.depends_on_calls, False)}."
            )
        )
    return FlowField(
        path=path,
        summary=text.segments(summary),
        origins=chips,
        origins_hidden=max(0, len(origins) - MAX_ORIGINS_SHOWN),
        notes=notes,
    )


def _origin(
    logic: FlowLogic, origin: Origin, text: _Text, depth: int = 0, copied: str | None = None
) -> FlowOrigin:
    return FlowOrigin(
        text=text.segments(origin_text(logic, origin, literals=False, certainty=False)),
        certainty=_CERTAINTY[origin_certainty(origin)],
        basis=_BASIS.get(origin.kind, "limit"),
        assumptions=origin_assumptions(origin) or None,
        evidence=_evidence(origin.source, text.guard),
        depth=depth,
        copied=copied,
    )


def _sources(
    logic: FlowLogic,
    lineage: FlowLineage,
    origin: Origin,
    level: int,
    expanded: set[str],
    budget: list[int],
    text: _Text,
) -> list[FlowOrigin]:
    """Where a copied field may come from, as for the page's indented lines."""
    if origin.kind is not OriginKind.COPY or origin.source_path is None:
        return []
    if not origin.source_origins or origin.id in expanded or level > MAX_COPY_DEPTH_SHOWN:
        return []
    expanded.add(origin.id)
    path = origin.source_path.text()
    found: list[FlowOrigin] = []
    for source_id in origin.source_origins[:MAX_SOURCE_ORIGINS]:
        if budget[0] <= 0:
            break
        budget[0] -= 1
        source = lineage.origin(source_id)
        found.append(_origin(logic, source, text, level, path))
        found += _sources(logic, lineage, source, level + 1, expanded, budget, text)
    return found


def _evidence(source: IrSourceReference | None, guard: TextGuard) -> SourceRef | None:
    if source is None:
        return None
    return SourceRef(
        path=guard.path(source.path),
        xml_path=guard.name(source.xml_path) if source.xml_path else None,
    )


# --- calls ---------------------------------------------------------------------------------------


def _call(logic: FlowLogic, call_id: str, refs: Mapping[str, str], text: _Text) -> FlowCall:
    call = logic.call(call_id)
    never = call.reach is Reach.UNREACHABLE
    level = Certainty.DERIVED if never else call.guard.certainty
    rules = call.unreachable_rules if never else sort_rules(call.guard.rules)
    return FlowCall(
        id=call.id,
        target=text.guard.name(call.target),
        target_id=refs.get(call.target) if call.target_status is TargetStatus.RESOLVED else None,
        how="transformer" if call.call_type is CallType.MAPINVOKE else "step",
        runs_when=text.segments(runs_when(logic, call)),
        certainty=_CERTAINTY[level],
        assumptions=assumption_label(rules) or None,
        reach=_REACH[call.reach],
    )


# --- scenarios -----------------------------------------------------------------------------------


def _scenario_tables(
    logic: FlowLogic, scenarios: FlowScenarios | None, text: _Text, budget: _Bytes
) -> list[FlowScenarioTable]:
    if scenarios is None:
        return []
    return [_table(logic, table, text, budget) for table in scenarios.tables]


def _table(
    logic: FlowLogic, table: ScenarioTable, text: _Text, budget: _Bytes
) -> FlowScenarioTable:
    def row(scenario: Scenario) -> FlowScenarioRow:
        calls = [scenario_call(logic, table, scenario, call_id) for call_id in scenario.call_ids]
        depends = [call_ref(logic, call_id) for call_id in scenario.depends_on_calls]
        return FlowScenarioRow(
            id=scenario.id,
            conditions=text.segments(outcomes_text(logic, scenario.outcomes)),
            calls=text.segments(", ".join(calls)),
            ends=text.segments(scenario_end(logic, scenario)),
            depends_on=text.segments(", ".join(depends)),
            feasibility=_FEASIBILITY[scenario.feasibility],
            assumptions=assumption_label(scenario.rules) or None,
        )

    rows, rows_hidden = _fit((row(scenario) for scenario in table.scenarios), budget)
    notes: list[str] = []
    if rows_hidden:
        notes.append(f"{rows_hidden} more scenario(s) are not shown, to keep this file small.")
    if not table.scenarios:
        notes.append(
            f"{', '.join(table.decision_ids)} depend on each other but are not combined: the "
            "limit on combinations followed per service was reached."
        )
    if table.walk_limit:
        notes.append(
            "Cut short: the limit on combinations followed per service was reached; further "
            "combinations are not shown."
        )
    elif table.truncated:
        notes.append(
            f"Cut short: at most {MAX_SCENARIOS} scenarios are listed; further combinations are "
            "not shown."
        )
    if table.left_out:
        notes.append(
            f"{', '.join(table.left_out)} also depend on these decisions and are not combined "
            f"(at most {MAX_CHAIN} in a row)."
        )
    for item in table.ruled_out[:MAX_RULED_SHOWN]:
        notes.append(f"Ruled out: {ruled_text(logic, item, literals=False)}.")
    if len(table.ruled_out) > MAX_RULED_SHOWN:
        notes.append(f"Ruled out: and {len(table.ruled_out) - MAX_RULED_SHOWN} more.")
    return FlowScenarioTable(
        decisions=list(table.decision_ids),
        rows=rows,
        notes=[text.segments(note) for note in notes],
    )


def _scenario_notes(scenarios: FlowScenarios | None, text: _Text) -> list[list[Segment]]:
    if scenarios is None:
        return []
    notes = []
    if scenarios.independent:
        notes.append(f"Not combined with another decision: {', '.join(scenarios.independent)}.")
    if scenarios.in_loops:
        notes.append(
            "Inside a loop, so each iteration may take another case; not combined: "
            f"{', '.join(scenarios.in_loops)}."
        )
    notes += [f"Scenario limit: {item}." for item in scenarios.limits]
    return [text.segments(note) for note in notes]
