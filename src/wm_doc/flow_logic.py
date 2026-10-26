"""Which steps of a FLOW service run under which conditions.

Derived facts, computed on demand from the parsed FLOW tree and never stored in
`analysis.json`. Nothing is evaluated: a case label is reported as written (under the
free-text policy), and every conclusion names the Integration Server rules it rests on
(`flow_semantics`). The model answers these questions per step:

- Decisions: each BRANCH, its cases with their conditions, whether a case can never run
  (an earlier case has the same label), which EXITs every path through a case may end with,
  and whether "no case matched" is possible.
- Calls: for every INVOKE and transformer, the conditions under which it runs (its guard):
  the cases it sits in, cases of earlier BRANCHes that must not have been taken because they
  always leave the enclosing step, TRY/CATCH and alternative sequences, loops and repeats.
- EXITs: where each one goes.
- Steps that never run, because an earlier step always leaves.

Soundness rules. A "normal run" is one in which no step fails on its own; failure paths are
modelled only where TRY/CATCH, EXIT-ON SUCCESS or EXIT-ON DONE make them explicit. A step is
called unreachable only when every normal path before it provably leaves; an EXIT whose target
cannot be determined (for example because labels are withheld) may go anywhere, so it never
proves anything. A step after a BRANCH never inherits that BRANCH's case.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from wm_doc.call_targets import TargetStatus, classify_target
from wm_doc.flow_paths import PipelineRef, expression_refs, path_ref
from wm_doc.ir import (
    CallType,
    FlowNode,
    FlowNodeType,
    FlowService,
    SourceReference,
    TextDisclosure,
)

MAX_DEPTH = 64
MAX_SAME_TARGET = 3

CALL_NODE_TYPES = {FlowNodeType.INVOKE: CallType.INVOKE, FlowNodeType.MAPINVOKE: CallType.MAPINVOKE}
FORMS = {"TRY", "CATCH", "FINALLY"}


class Certainty(StrEnum):
    OBSERVED = "observed"
    DERIVED = "derived"
    POSSIBLE = "possible"
    UNKNOWN = "unknown"


_CERTAINTY_RANK = {
    Certainty.OBSERVED: 0,
    Certainty.DERIVED: 1,
    Certainty.POSSIBLE: 2,
    Certainty.UNKNOWN: 3,
}


def weakest(certainties: Iterable[Certainty]) -> Certainty:
    """The least certain of `certainties`; OBSERVED when there are none."""
    return max(certainties, key=_CERTAINTY_RANK.__getitem__, default=Certainty.OBSERVED)


class ConditionKind(StrEnum):
    VALUE = "value"  # the switch value equals the label
    NULL = "null"  # $null: the switch variable is missing or null
    EMPTY = "empty"  # a blank label in switch mode
    PATTERN = "pattern"  # /regex/ label in switch mode
    EXPRESSION = "expression"  # a label expression
    DEFAULT = "default"  # $default
    UNLABELLED = "unlabelled"  # a blank label in expression mode
    WITHHELD = "withheld"  # the label exists but the free-text policy hides it


@dataclass(frozen=True, slots=True)
class CaseCondition:
    kind: ConditionKind
    text: str | None = None  # the label as written; only when the policy includes it
    refs: tuple[PipelineRef, ...] = ()  # fields an expression refers to (never evaluated)
    refs_parsed: bool = True  # False when an expression could not be split reliably


class GuardKind(StrEnum):
    IN_CASE = "in_case"  # inside a case of a BRANCH
    NOT_CASES = "not_cases"  # earlier cases that always leave must not have been taken
    ON_FAILURE_OF = "on_failure_of"  # CATCH, or a later alternative of an EXIT-ON SUCCESS step
    ONLY_IF_SUCCEEDED = "only_if_succeeded"  # after a TRY/alternatives whose fallbacks leave
    FINALLY = "finally"
    PER_ITERATION = "per_iteration"
    PER_ATTEMPT = "per_attempt"
    MAY_BE_SKIPPED = "may_be_skipped"  # an earlier EXIT on some paths leaves the enclosing step
    NOT_ANALYSED = "not_analysed"  # nested deeper than MAX_DEPTH


@dataclass(frozen=True, slots=True)
class GuardTerm:
    kind: GuardKind
    node_id: str  # the step that introduces the condition
    certainty: Certainty
    rules: tuple[str, ...] = ()
    decision_id: str | None = None
    case_ids: tuple[str, ...] = ()
    step_ids: tuple[str, ...] = ()  # steps that must fail (ON_FAILURE_OF) or succeed
    exit_ids: tuple[str, ...] = ()
    loop_path: PipelineRef | None = None


@dataclass(frozen=True, slots=True)
class Guard:
    terms: tuple[GuardTerm, ...] = ()

    def extend(self, *terms: GuardTerm) -> Guard:
        return Guard(self.terms + terms) if terms else self

    @property
    def certainty(self) -> Certainty:
        return weakest(term.certainty for term in self.terms)

    @property
    def rules(self) -> tuple[str, ...]:
        return sort_rules(rule for term in self.terms for rule in term.rules)


class ExitScope(StrEnum):
    FLOW = "$flow"
    PARENT = "$parent"
    LOOP = "$loop"
    LABEL = "label"


@dataclass(frozen=True, slots=True)
class ExitEffect:
    id: str  # E1, E2, ... in document order
    node_id: str
    scope: ExitScope
    signal: str  # SUCCESS, FAILURE or the raw value
    target_id: str | None  # the step it leaves; None when it cannot be determined
    reach_id: str | None  # how far it takes control: for FAILURE, up to the failure handler
    certainty: Certainty
    rules: tuple[str, ...]
    note: str | None
    guard: Guard
    source: SourceReference


@dataclass(frozen=True, slots=True)
class DecisionCase:
    id: str  # D1.c1
    index: int
    node_id: str  # the BRANCH_CASE node
    step_id: str | None  # the step that forms the case
    condition: CaseCondition
    excludes: tuple[str, ...]  # earlier cases that must not have matched
    unreachable_rule: str | None  # set when the case can never run
    ends_with: tuple[str, ...]  # when every path through the case leaves the BRANCH: those EXITs
    call_ids: tuple[str, ...]
    source: SourceReference


class DecisionMode(StrEnum):
    SWITCH = "switch"
    EXPRESSIONS = "expressions"


@dataclass(frozen=True, slots=True)
class Decision:
    id: str  # D1, D2, ... in document order
    node_id: str
    mode: DecisionMode
    switch: PipelineRef | None
    cases: tuple[DecisionCase, ...]
    has_default: bool
    falls_through: bool  # "no case matched" is possible
    guard: Guard
    loop_id: str | None  # innermost enclosing LOOP/REPEAT; exclusive per iteration only
    notes: tuple[str, ...]
    source: SourceReference


class Reach(StrEnum):
    NORMAL = "normal"  # runs on every normal run
    CONDITIONAL = "conditional"
    FAILURE_PATH = "failure_path"  # only after something failed
    UNREACHABLE = "unreachable"


@dataclass(frozen=True, slots=True)
class CallContext:
    id: str  # C1, C2, ... in document order
    call_occurrence_id: str
    node_id: str
    target: str
    call_type: CallType
    target_status: TargetStatus
    index: int
    guard: Guard
    reach: Reach
    unreachable_rules: tuple[str, ...]  # rules behind "never runs"
    same_target_as: tuple[str, ...]  # up to MAX_SAME_TARGET other calls to the same service
    same_target_count: int  # how many other calls go to the same service
    source: SourceReference


@dataclass(frozen=True, slots=True)
class UnreachableStep:
    node_id: str
    kind: FlowNodeType
    reason: str  # "after_exit" or "duplicate_case"
    exit_ids: tuple[str, ...]
    case_id: str | None
    rules: tuple[str, ...]
    source: SourceReference


@dataclass(frozen=True)
class FlowLogic:
    service: str
    significant: bool  # BRANCH, EXIT, TRY/CATCH or a non-default EXIT-ON is present
    decisions: tuple[Decision, ...]
    calls: tuple[CallContext, ...]
    exits: tuple[ExitEffect, ...]
    unreachable: tuple[UnreachableStep, ...]
    limits: tuple[str, ...]
    step_text: dict[str, str]  # node id -> how a reader finds the step (policy-safe)
    _decisions: dict[str, Decision] = field(init=False, repr=False, compare=False)
    _cases: dict[str, DecisionCase] = field(init=False, repr=False, compare=False)
    _exits: dict[str, ExitEffect] = field(init=False, repr=False, compare=False)
    _calls: dict[str, CallContext] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_decisions", {item.id: item for item in self.decisions})
        cases = {case.id: case for item in self.decisions for case in item.cases}
        object.__setattr__(self, "_cases", cases)
        object.__setattr__(self, "_exits", {item.id: item for item in self.exits})
        object.__setattr__(self, "_calls", {item.id: item for item in self.calls})

    def decision(self, decision_id: str) -> Decision:
        return self._decisions[decision_id]

    def case(self, case_id: str) -> DecisionCase:
        return self._cases[case_id]

    def exit(self, exit_id: str) -> ExitEffect:
        return self._exits[exit_id]

    def call(self, call_id: str) -> CallContext:
        return self._calls[call_id]


def compute_flow_logic(service: FlowService) -> FlowLogic | None:
    """The conditional structure of a FLOW service; None for services without a FLOW tree."""
    if service.flow_tree is None:
        return None
    return _Analysis(service, service.flow_tree).run()


def sort_rules(rules: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(rules), key=lambda rule: int(rule[1:])))


# --- implementation ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Outcome:
    """What can happen when a step runs on a normal run."""

    completes: bool  # some path finishes the step and continues after it
    leaves: frozenset[str]  # EXITs (node ids) that may take control above the step


_COMPLETES = _Outcome(True, frozenset())


class _Analysis:
    def __init__(self, service: FlowService, root: FlowNode) -> None:
        self.service = service
        self.root = root
        self.nodes: dict[str, FlowNode] = {}
        self.parent: dict[str, FlowNode | None] = {}
        self.ancestors: dict[str, frozenset[str]] = {}
        self.order: list[FlowNode] = []
        self._index(root, None, frozenset())
        self.position = {node.id: index for index, node in enumerate(self.order)}
        self.occurrences = {call.id: call for call in service.call_occurrences}
        self.decision_ids: dict[str, str] = {}
        self.case_ids: dict[str, str] = {}
        self.call_ids: dict[str, str] = {}
        self.exit_ids: dict[str, str] = {}
        for node in self.order:
            if node.type is FlowNodeType.BRANCH:
                decision_id = f"D{len(self.decision_ids) + 1}"
                self.decision_ids[node.id] = decision_id
                cases = [child for child in node.children if child.type is FlowNodeType.BRANCH_CASE]
                for number, case in enumerate(cases, 1):
                    self.case_ids[case.id] = f"{decision_id}.c{number}"
            elif node.type in CALL_NODE_TYPES and node.call_occurrence_id in self.occurrences:
                self.call_ids[node.id] = f"C{len(self.call_ids) + 1}"
            elif node.type is FlowNodeType.EXIT:
                self.exit_ids[node.id] = f"E{len(self.exit_ids) + 1}"
        self.exit_targets: dict[str, tuple[str | None, str | None, ExitScope]] = {
            node.id: self._exit_target(node)
            for node in self.order
            if node.type is FlowNodeType.EXIT
        }
        # How far each EXIT takes control: its target, or for FAILURE the step that fails up to
        # the nearest step that handles failures (S10, S13).
        self.reach: dict[str, str | None] = {
            exit_id: self._exit_reach(exit_id, target)
            for exit_id, (target, _note, _scope) in self.exit_targets.items()
        }
        self.conditions: dict[str, CaseCondition] = {}
        self.unreachable_cases: dict[str, str] = {}
        self.decision_info: dict[str, tuple[DecisionMode, list[str]]] = {}
        for node in self.order:
            if node.type is FlowNodeType.BRANCH:
                self._prepare_decision(node)
        self._outcomes: dict[str, _Outcome] = {}
        self.call_contexts: dict[str, CallContext] = {}
        self.exit_effects: dict[str, ExitEffect] = {}
        self.decision_guards: dict[str, Guard] = {}
        self.loop_of: dict[str, str] = {}
        self.unreachable: list[UnreachableStep] = []
        self.too_deep = False

    # indexing -------------------------------------------------------------------------------

    def _index(self, node: FlowNode, parent: FlowNode | None, ancestors: frozenset[str]) -> None:
        self.nodes[node.id] = node
        self.parent[node.id] = parent
        self.ancestors[node.id] = ancestors
        self.order.append(node)
        inner = ancestors | {node.id}
        for child in node.children:
            self._index(child, node, inner)

    def _above(self, ancestor_id: str | None, node_id: str) -> bool:
        """True when `ancestor_id` is a strict ancestor of `node_id`."""
        return ancestor_id is not None and ancestor_id in self.ancestors[node_id]

    def _exit_names(self, node_ids: Iterable[str]) -> tuple[str, ...]:
        return tuple(
            self.exit_ids[item] for item in sorted(node_ids, key=self.position.__getitem__)
        )

    # EXIT targets --------------------------------------------------------------------------

    def _exit_target(self, node: FlowNode) -> tuple[str | None, str | None, ExitScope]:
        raw = (node.exit_from or "$parent").strip()
        parent = self.parent[node.id]
        if raw == "$flow":
            return self.root.id, None, ExitScope.FLOW
        if raw == "$parent":
            # A case is a synthetic node: an EXIT that is itself a BRANCH child leaves the
            # BRANCH (S30, checked by V10).
            while parent is not None and parent.type is FlowNodeType.BRANCH_CASE:
                parent = self.parent[parent.id]
            return (parent.id if parent else None), None, ExitScope.PARENT
        if raw == "$loop":
            while parent is not None and parent.type not in (
                FlowNodeType.LOOP,
                FlowNodeType.REPEAT,
            ):
                parent = self.parent[parent.id]
            if parent is None:
                return None, "no enclosing LOOP or REPEAT", ExitScope.LOOP
            return parent.id, None, ExitScope.LOOP
        withheld = False
        while parent is not None:
            label = parent.label
            if parent.type is not FlowNodeType.BRANCH_CASE and label is not None:
                if label.disclosure is TextDisclosure.INCLUDED and label.value is not None:
                    if label.value.strip() == raw:
                        return parent.id, None, ExitScope.LABEL
                else:
                    withheld = True
            parent = self.parent[parent.id]
        note = "the step labels are withheld" if withheld else "no enclosing step has that label"
        return None, note, ExitScope.LABEL

    def _exit_reach(self, exit_id: str, target: str | None) -> str | None:
        if target is None:
            return None
        node = self.nodes[exit_id]
        if (node.signal or "SUCCESS").strip().upper() != "FAILURE":
            return target
        current = self.nodes[target]
        while True:
            parent = self.parent[current.id]
            if parent is None:
                return current.id  # the service fails
            if parent.type is FlowNodeType.REPEAT:
                return None  # a retry may take another path: where it ends is unknown
            if _handles_failure_of(parent, current):
                return current.id
            current = parent

    # decisions -----------------------------------------------------------------------------

    def _prepare_decision(self, node: FlowNode) -> None:
        mode = DecisionMode.EXPRESSIONS if node.evaluate_labels else DecisionMode.SWITCH
        notes: list[str] = []
        if mode is DecisionMode.EXPRESSIONS and node.switch:
            notes.append("SWITCH_IGNORED")
        if mode is DecisionMode.SWITCH and not node.switch:
            notes.append("NO_SWITCH")
        cases = [child for child in node.children if child.type is FlowNodeType.BRANCH_CASE]
        seen: set[tuple[ConditionKind, str | None]] = set()
        default_seen = False
        for position, case in enumerate(cases):
            condition = _condition(case, mode)
            self.conditions[case.id] = condition
            if condition.kind is ConditionKind.DEFAULT:
                if default_seen:
                    self.unreachable_cases[case.id] = "S6"
                default_seen = True
                if position != len(cases) - 1:
                    notes.append("DEFAULT_NOT_LAST")
            elif mode is DecisionMode.SWITCH and condition.kind in _COMPARABLE:
                key = (condition.kind, condition.text)
                if key in seen:
                    self.unreachable_cases[case.id] = "S2"
                    notes.append("DUPLICATE_LABEL")
                seen.add(key)
            if condition.kind is ConditionKind.WITHHELD:
                notes.append("LABELS_WITHHELD")
            if condition.kind is ConditionKind.EXPRESSION and not condition.refs_parsed:
                notes.append("EXPRESSION_NOT_SPLIT")
        self.decision_info[node.id] = (mode, list(dict.fromkeys(notes)))

    def _case_term(self, branch: FlowNode, case: FlowNode) -> GuardTerm:
        mode, notes = self.decision_info[branch.id]
        condition = self.conditions[case.id]
        if condition.kind is ConditionKind.UNLABELLED:
            certainty = Certainty.UNKNOWN
        elif "NO_SWITCH" in notes:
            certainty = Certainty.POSSIBLE
        else:
            certainty = Certainty.DERIVED
        return GuardTerm(
            kind=GuardKind.IN_CASE,
            node_id=branch.id,
            certainty=certainty,
            rules=case_rules(mode, condition.kind),
            decision_id=self.decision_ids[branch.id],
            case_ids=(self.case_ids[case.id],),
        )

    def _has_default(self, branch: FlowNode) -> bool:
        return any(
            self.conditions[child.id].kind is ConditionKind.DEFAULT
            for child in branch.children
            if child.type is FlowNodeType.BRANCH_CASE
        )

    def _live_cases(self, branch: FlowNode) -> list[FlowNode]:
        return [
            child
            for child in branch.children
            if child.type is FlowNodeType.BRANCH_CASE and child.id not in self.unreachable_cases
        ]

    # outcomes ------------------------------------------------------------------------------

    def _lift(self, outcome: _Outcome, node: FlowNode) -> tuple[bool, frozenset[str]]:
        """Seen from `node`: (an EXIT may finish `node` itself, EXITs that may leave it)."""
        finishes = False
        leaving: set[str] = set()
        for exit_id in outcome.leaves:
            reach = self.reach[exit_id]
            if reach is None:
                finishes = True  # it may go anywhere, including here
                leaving.add(exit_id)
            elif reach == node.id:
                finishes = True
            else:
                leaving.add(exit_id)
        return finishes, frozenset(leaving)

    def outcome(self, node: FlowNode) -> _Outcome:
        if node.id not in self._outcomes:
            self._outcomes[node.id] = self._compute_outcome(node)
        return self._outcomes[node.id]

    def _compute_outcome(self, node: FlowNode) -> _Outcome:
        kind = node.type
        if kind is FlowNodeType.EXIT:
            return _Outcome(False, frozenset({node.id}))
        if kind is FlowNodeType.BRANCH_CASE:
            if not node.children:
                return _COMPLETES
            finishes, leaving = self._lift(self.outcome(node.children[0]), node)
            return _Outcome(self.outcome(node.children[0]).completes or finishes, leaving)
        if kind is FlowNodeType.BRANCH:
            completes = not self._has_default(node)  # "no case matched" finishes the BRANCH (S7)
            leaving_all: set[str] = set()
            for case in self._live_cases(node):
                case_outcome = self.outcome(case)
                finishes, leaving = self._lift(case_outcome, node)
                completes = completes or case_outcome.completes or finishes
                leaving_all |= leaving
            return _Outcome(completes, frozenset(leaving_all))
        if kind is FlowNodeType.LOOP:
            _completes, finishes, leaving = self._sequence_outcome(node)
            return _Outcome(True, leaving)  # a LOOP may run zero times (S29)
        if kind is FlowNodeType.SEQUENCE and _is_alternatives(node):
            completes = False
            leaving_all = set()
            finally_completes = True
            finally_finishes = False
            for child in node.children:
                child_outcome = self.outcome(child)
                finishes, leaving = self._lift(child_outcome, node)
                leaving_all |= leaving
                if _form(child) == "FINALLY":
                    finally_completes = child_outcome.completes or finishes
                    finally_finishes = finishes  # it may replace a pending EXIT (S13)
                else:
                    completes = completes or child_outcome.completes or finishes
            return _Outcome(
                (completes and finally_completes) or finally_finishes, frozenset(leaving_all)
            )
        if kind in (FlowNodeType.FLOW, FlowNodeType.SEQUENCE, FlowNodeType.REPEAT):
            completes, finishes, leaving = self._sequence_outcome(node)
            return _Outcome(completes or finishes, leaving)
        return _COMPLETES  # MAP, INVOKE and transformers hold no EXIT

    def _sequence_outcome(self, node: FlowNode) -> tuple[bool, bool, frozenset[str]]:
        """(the end of the children is reached, an EXIT finishes `node`, EXITs leaving it)."""
        done = _exit_on(node) == "DONE"
        finishes = False
        leaving_all: set[str] = set()
        for child in node.children:
            child_outcome = self.outcome(child)
            child_finishes, leaving = self._lift(child_outcome, node)
            finishes = finishes or child_finishes
            leaving_all |= leaving
            if _form(child) == "CATCH":
                continue  # skipped on a normal run
            if not child_outcome.completes and not done:
                return False, finishes, frozenset(leaving_all)
        return True, finishes, frozenset(leaving_all)

    def _always_leaves(self, node: FlowNode, owner: FlowNode, enclosing: FlowNode) -> bool:
        """True when every normal path through `node` leaves `owner` and also `enclosing`."""
        outcome = self.outcome(node)
        if outcome.completes or not outcome.leaves:
            return False
        for exit_id in outcome.leaves:
            reach = self.reach[exit_id]
            if reach is None or reach == owner.id:
                return False
            if reach != enclosing.id and not self._above(reach, enclosing.id):
                return False
        return True

    # guards --------------------------------------------------------------------------------

    def run(self) -> FlowLogic:
        self._walk(self.root, Guard(), 0, None, None)
        limits = []
        if self.too_deep:
            limits.append(f"steps nested deeper than {MAX_DEPTH} levels are not analysed")
        return FlowLogic(
            service=self.service.identity.full_name,
            significant=any(_is_significant(node) for node in self.order),
            decisions=tuple(
                self._decision(node) for node in self.order if node.id in self.decision_ids
            ),
            calls=self._finish_calls(),
            exits=tuple(
                self.exit_effects[node.id] for node in self.order if node.id in self.exit_effects
            ),
            unreachable=tuple(self.unreachable),
            limits=tuple(limits),
            step_text={node.id: self._step_text(node) for node in self.order},
        )

    def _walk(
        self,
        node: FlowNode,
        guard: Guard,
        depth: int,
        blocked: tuple[tuple[str, ...], tuple[str, ...]] | None,
        loop_id: str | None,
    ) -> None:
        """Record calls, EXITs and BRANCHes under `node`.

        `blocked` is (EXIT ids, rules) when every normal path before `node` leaves first.
        """
        if depth > MAX_DEPTH:
            self.too_deep = True
            term = GuardTerm(GuardKind.NOT_ANALYSED, node.id, Certainty.UNKNOWN)
            for inner in _subtree(node):
                self._record(inner, guard.extend(term), blocked, loop_id)
            return
        self._record(node, guard, blocked, loop_id)
        kind = node.type
        if kind is FlowNodeType.BRANCH:
            self._walk_branch(node, guard, depth, blocked, loop_id)
        elif kind is FlowNodeType.LOOP:
            leaving = self._loop_leavers(node)
            term = GuardTerm(
                GuardKind.PER_ITERATION,
                node.id,
                Certainty.POSSIBLE if leaving else Certainty.DERIVED,
                ("S22", "S12") if leaving else ("S22",),
                exit_ids=leaving,
                loop_path=path_ref(node.in_array),
            )
            self._walk_sequence(node, guard.extend(term), depth, blocked, node.id)
        elif kind is FlowNodeType.REPEAT:
            leaving = self._loop_leavers(node)
            term = GuardTerm(
                GuardKind.PER_ATTEMPT,
                node.id,
                Certainty.POSSIBLE if leaving else Certainty.DERIVED,
                ("S23",),
                exit_ids=leaving,
            )
            self._walk_sequence(node, guard.extend(term), depth, blocked, node.id)
        elif kind is FlowNodeType.SEQUENCE and _is_alternatives(node):
            self._walk_alternatives(node, guard, depth, blocked, loop_id)
        elif kind in (FlowNodeType.FLOW, FlowNodeType.SEQUENCE):
            self._walk_sequence(node, guard, depth, blocked, loop_id)
        else:
            for child in node.children:
                self._walk(child, guard, depth + 1, blocked, loop_id)

    def _loop_leavers(self, node: FlowNode) -> tuple[str, ...]:
        """EXITs inside a LOOP or REPEAT that may end it early (or go somewhere unknown)."""
        found = []
        for inner in _subtree(node):
            if inner.type is FlowNodeType.EXIT:
                reach = self.reach[inner.id]
                if reach is None or reach == node.id or self._above(reach, node.id):
                    found.append(inner.id)
        return self._exit_names(found)

    def _record(
        self,
        node: FlowNode,
        guard: Guard,
        blocked: tuple[tuple[str, ...], tuple[str, ...]] | None,
        loop_id: str | None,
    ) -> None:
        if node.id in self.call_ids and node.id not in self.call_contexts:
            occurrence = self.occurrences[node.call_occurrence_id or ""]
            target = node.target or occurrence.target
            self.call_contexts[node.id] = CallContext(
                id=self.call_ids[node.id],
                call_occurrence_id=occurrence.id,
                node_id=node.id,
                target=target,
                call_type=CALL_NODE_TYPES[node.type],
                target_status=classify_target(target, occurrence.resolved),
                index=int(self.call_ids[node.id][1:]),
                guard=guard,
                reach=_reach(guard, blocked is not None),
                unreachable_rules=blocked[1] if blocked is not None else (),
                same_target_as=(),
                same_target_count=0,
                source=node.source,
            )
        elif node.type is FlowNodeType.EXIT and node.id not in self.exit_effects:
            exit_target, note, scope = self.exit_targets[node.id]
            target_node = self.nodes.get(exit_target or "")
            rules = ["S11"]
            if scope is ExitScope.PARENT and _parent_is_case(self.parent[node.id]):
                rules.append("S30")
            if target_node is not None and target_node.type in (
                FlowNodeType.LOOP,
                FlowNodeType.REPEAT,
            ):
                rules.append("S12")
            signal = (node.signal or "SUCCESS").strip().upper()
            if signal == "FAILURE":
                rules.append("S10")
            self.exit_effects[node.id] = ExitEffect(
                id=self.exit_ids[node.id],
                node_id=node.id,
                scope=scope,
                signal=signal,
                target_id=exit_target,
                reach_id=self.reach[node.id],
                certainty=Certainty.DERIVED if exit_target is not None else Certainty.UNKNOWN,
                rules=sort_rules(rules),
                note=note,
                guard=guard,
                source=node.source,
            )
        elif node.type is FlowNodeType.BRANCH and node.id not in self.decision_guards:
            self.decision_guards[node.id] = guard
            if loop_id is not None:
                self.loop_of[node.id] = loop_id

    def _walk_branch(
        self,
        node: FlowNode,
        guard: Guard,
        depth: int,
        blocked: tuple[tuple[str, ...], tuple[str, ...]] | None,
        loop_id: str | None,
    ) -> None:
        for case in node.children:
            if case.type is not FlowNodeType.BRANCH_CASE:
                self._walk(case, guard, depth + 1, blocked, loop_id)
                continue
            case_blocked = blocked
            if case.id in self.unreachable_cases:
                rule_id = self.unreachable_cases[case.id]
                case_blocked = blocked or ((), (rule_id,))
                self.unreachable.append(
                    UnreachableStep(
                        node_id=case.id,
                        kind=FlowNodeType.BRANCH_CASE,
                        reason="duplicate_case",
                        exit_ids=(),
                        case_id=self.case_ids[case.id],
                        rules=(rule_id,),
                        source=case.source,
                    )
                )
            inner = guard.extend(self._case_term(node, case))
            for child in case.children:
                self._walk(child, inner, depth + 1, case_blocked, loop_id)

    def _walk_sequence(
        self,
        node: FlowNode,
        guard: Guard,
        depth: int,
        blocked: tuple[tuple[str, ...], tuple[str, ...]] | None,
        loop_id: str | None,
    ) -> None:
        """Children run in order; earlier EXITs may skip or block the later ones."""
        done = _exit_on(node) == "DONE"
        current = guard
        local_block = blocked
        tries: list[str] = []
        for child in node.children:
            form = _form(child)
            child_guard = current
            if form == "CATCH":
                child_guard = current.extend(
                    GuardTerm(
                        GuardKind.ON_FAILURE_OF,
                        node.id,
                        Certainty.DERIVED,
                        ("S13", "S14"),
                        step_ids=tuple(tries),
                    )
                )
            elif form == "FINALLY":
                child_guard = current.extend(
                    GuardTerm(GuardKind.FINALLY, node.id, Certainty.DERIVED, ("S13", "S14"))
                )
            if local_block is not None and blocked is None:
                self.unreachable.append(
                    UnreachableStep(
                        node_id=child.id,
                        kind=child.type,
                        reason="after_exit",
                        exit_ids=local_block[0],
                        case_id=None,
                        rules=local_block[1],
                        source=child.source,
                    )
                )
            self._walk(child, child_guard, depth + 1, local_block, loop_id)
            if form == "TRY":
                tries.append(child.id)
            if local_block is not None:
                continue
            outcome = self.outcome(child)
            if form == "CATCH":
                current = current.extend(*self._after_catch(child, node, tries))
                continue
            if not outcome.completes and not done:
                local_block = (self._exit_names(outcome.leaves), self._block_rules(child))
                continue
            if not outcome.completes and done:
                current = current.extend(self._skip_term(child, outcome.leaves))
                continue
            current = current.extend(*self._after_terms(child, node))

    def _block_rules(self, child: FlowNode) -> tuple[str, ...]:
        """Rules behind "everything after `child` never runs"."""
        rules = ["S10", "S11"]
        if any(
            inner.type is FlowNodeType.BRANCH and self._has_default(inner)
            for inner in _subtree(child)
        ):
            rules.append("S6")  # the BRANCH cannot fall through only because of its $default
        if any(_parent_is_case(self.parent[item]) for item in self.outcome(child).leaves):
            rules.append("S30")
        return sort_rules(rules)

    def _skip_term(self, child: FlowNode, exits: Iterable[str]) -> GuardTerm:
        return GuardTerm(
            GuardKind.MAY_BE_SKIPPED,
            child.id,
            Certainty.POSSIBLE,
            ("S11",),
            exit_ids=self._exit_names(exits),
        )

    def _after_catch(self, catch: FlowNode, parent: FlowNode, tries: list[str]) -> list[GuardTerm]:
        """After a CATCH that always leaves, later steps run only when the TRY succeeded."""
        outcome = self.outcome(catch)
        if tries and self._always_leaves(catch, catch, parent):
            return [
                GuardTerm(
                    GuardKind.ONLY_IF_SUCCEEDED,
                    catch.id,
                    Certainty.DERIVED,
                    ("S13", "S14"),
                    step_ids=tuple(tries),
                    exit_ids=self._exit_names(outcome.leaves),
                )
            ]
        return [self._skip_term(catch, outcome.leaves)] if outcome.leaves else []

    def _after_terms(self, child: FlowNode, parent: FlowNode) -> list[GuardTerm]:
        """Conditions a later sibling of `child` gets because `child` may leave `parent`."""
        terms: list[GuardTerm] = []
        explained: set[str] = set()
        if child.type is FlowNodeType.BRANCH:
            exiting: list[str] = []
            for case in self._live_cases(child):
                if self._always_leaves(case, child, parent):
                    exiting.append(self.case_ids[case.id])
                    explained |= self.outcome(case).leaves
            if exiting:
                terms.append(
                    GuardTerm(
                        GuardKind.NOT_CASES,
                        child.id,
                        Certainty.DERIVED,
                        ("S1", "S11"),
                        decision_id=self.decision_ids[child.id],
                        case_ids=tuple(exiting),
                        exit_ids=self._exit_names(explained),
                    )
                )
        elif child.type is FlowNodeType.SEQUENCE and _is_alternatives(child):
            alternatives = [item for item in child.children if _form(item) != "FINALLY"]
            if len(alternatives) > 1:
                first, rest = alternatives[0], alternatives[1:]
                if all(self._always_leaves(item, child, parent) for item in rest):
                    for item in rest:
                        explained |= self.outcome(item).leaves
                    terms.append(
                        GuardTerm(
                            GuardKind.ONLY_IF_SUCCEEDED,
                            child.id,
                            Certainty.DERIVED,
                            ("S13", "S14") if _form(first) == "TRY" else ("S10",),
                            step_ids=(first.id,),
                            exit_ids=self._exit_names(explained),
                        )
                    )
        skipping = [item for item in self.outcome(child).leaves if item not in explained]
        if skipping:
            terms.append(self._skip_term(child, skipping))
        return terms

    def _walk_alternatives(
        self,
        node: FlowNode,
        guard: Guard,
        depth: int,
        blocked: tuple[tuple[str, ...], tuple[str, ...]] | None,
        loop_id: str | None,
    ) -> None:
        """EXIT-ON SUCCESS: a later child runs only when every earlier one failed (S10).

        TRY/CATCH/FINALLY written as FORM sequences inside it are read the same way: CATCH runs
        when TRY failed, FINALLY runs after them (S13, S14).
        """
        earlier: list[str] = []
        for child in node.children:
            form = _form(child)
            if form == "FINALLY":
                term = GuardTerm(GuardKind.FINALLY, node.id, Certainty.DERIVED, ("S13", "S14"))
                self._walk(child, guard.extend(term), depth + 1, blocked, loop_id)
                continue
            inner = guard
            if earlier:
                inner = guard.extend(
                    GuardTerm(
                        GuardKind.ON_FAILURE_OF,
                        node.id,
                        Certainty.DERIVED,
                        ("S13", "S14") if form == "CATCH" else ("S10",),
                        step_ids=tuple(earlier),
                    )
                )
            self._walk(child, inner, depth + 1, blocked, loop_id)
            earlier.append(child.id)

    # results -------------------------------------------------------------------------------

    def _decision(self, node: FlowNode) -> Decision:
        mode, notes = self.decision_info[node.id]
        cases = [child for child in node.children if child.type is FlowNodeType.BRANCH_CASE]
        built: list[DecisionCase] = []
        earlier: list[str] = []
        after_pattern = False
        for position, case in enumerate(cases, 1):
            case_id = self.case_ids[case.id]
            condition = self.conditions[case.id]
            if condition.kind is ConditionKind.DEFAULT:
                excludes = tuple(self.case_ids[other.id] for other in cases if other is not case)
            elif mode is DecisionMode.EXPRESSIONS or after_pattern:
                excludes = tuple(earlier)
            else:
                excludes = ()
            if condition.kind is ConditionKind.PATTERN:
                after_pattern = True
            outcome = self.outcome(case)
            ends = () if outcome.completes else self._exit_names(outcome.leaves)
            built.append(
                DecisionCase(
                    id=case_id,
                    index=position,
                    node_id=case.id,
                    step_id=case.children[0].id if case.children else None,
                    condition=condition,
                    excludes=excludes,
                    unreachable_rule=self.unreachable_cases.get(case.id),
                    ends_with=ends,
                    call_ids=tuple(
                        self.call_ids[inner.id]
                        for inner in _subtree(case)
                        if inner.id in self.call_ids
                    ),
                    source=case.source,
                )
            )
            earlier.append(case_id)
        has_default = any(item.condition.kind is ConditionKind.DEFAULT for item in built)
        return Decision(
            id=self.decision_ids[node.id],
            node_id=node.id,
            mode=mode,
            switch=path_ref(node.switch),
            cases=tuple(built),
            has_default=has_default,
            falls_through=not has_default,
            guard=self.decision_guards.get(node.id, Guard()),
            loop_id=self.loop_of.get(node.id),
            notes=tuple(notes),
            source=node.source,
        )

    def _finish_calls(self) -> tuple[CallContext, ...]:
        ordered = sorted(self.call_contexts.values(), key=lambda item: item.index)
        by_target: dict[str, list[str]] = {}
        for call in ordered:
            by_target.setdefault(call.target, []).append(call.id)
        result = []
        for call in ordered:
            others = [item for item in by_target[call.target] if item != call.id]
            result.append(
                CallContext(
                    id=call.id,
                    call_occurrence_id=call.call_occurrence_id,
                    node_id=call.node_id,
                    target=call.target,
                    call_type=call.call_type,
                    target_status=call.target_status,
                    index=call.index,
                    guard=call.guard,
                    reach=call.reach,
                    unreachable_rules=call.unreachable_rules,
                    same_target_as=tuple(others[:MAX_SAME_TARGET]),
                    same_target_count=len(others),
                    source=call.source,
                )
            )
        return tuple(result)

    def _step_text(self, node: FlowNode) -> str:
        """A policy-safe way to name a step: kind, label in a code span, line."""
        if node is self.root:
            return "the service"
        label = node.label
        visible = label.value if label and label.disclosure is TextDisclosure.INCLUDED else None
        kind = _STEP_NAMES.get(node.type, node.type.value)
        form = _form(node)
        if form:
            kind = f"{form} block"
        line = f" (line {node.source.line})" if node.source.line else ""
        if visible:
            return f"the {kind} {code_span(visible)}{line}"
        if label is not None:
            return f"the {kind}{line} (label withheld)"
        return f"the {kind}{line}"


MAX_LABEL_CHARS = 120


def code_span(text: str) -> str:
    """`text` flattened, shortened and in a code span, so it cannot form Markdown structure."""
    flat = " ".join(text.split()).replace("`", "'")
    if len(flat) > MAX_LABEL_CHARS:
        return f"`{flat[: MAX_LABEL_CHARS - 3]}...` (shortened)"
    return f"`{flat}`"


_COMPARABLE = {ConditionKind.VALUE, ConditionKind.NULL, ConditionKind.EMPTY, ConditionKind.PATTERN}

_STEP_NAMES = {
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

# Rules behind "this case runs when its condition holds", by mode and condition kind.
_CONDITION_RULES: dict[tuple[DecisionMode, ConditionKind], tuple[str, ...]] = {
    (DecisionMode.SWITCH, ConditionKind.VALUE): ("S2",),
    (DecisionMode.SWITCH, ConditionKind.NULL): ("S3",),
    (DecisionMode.SWITCH, ConditionKind.EMPTY): ("S4",),
    (DecisionMode.SWITCH, ConditionKind.PATTERN): ("S5", "S2"),
    (DecisionMode.SWITCH, ConditionKind.DEFAULT): ("S6",),
    (DecisionMode.SWITCH, ConditionKind.WITHHELD): ("S2",),
    (DecisionMode.SWITCH, ConditionKind.UNLABELLED): ("S4",),
    (DecisionMode.SWITCH, ConditionKind.EXPRESSION): ("S2",),
    (DecisionMode.EXPRESSIONS, ConditionKind.EXPRESSION): ("S8",),
    (DecisionMode.EXPRESSIONS, ConditionKind.DEFAULT): ("S6", "S8"),
    (DecisionMode.EXPRESSIONS, ConditionKind.WITHHELD): ("S8",),
    (DecisionMode.EXPRESSIONS, ConditionKind.UNLABELLED): ("S8",),
    (DecisionMode.EXPRESSIONS, ConditionKind.VALUE): ("S8",),
    (DecisionMode.EXPRESSIONS, ConditionKind.NULL): ("S8",),
    (DecisionMode.EXPRESSIONS, ConditionKind.EMPTY): ("S8",),
    (DecisionMode.EXPRESSIONS, ConditionKind.PATTERN): ("S8",),
}


def case_rules(mode: DecisionMode, kind: ConditionKind) -> tuple[str, ...]:
    """The IS rules behind "this case runs only when its condition holds"."""
    return sort_rules(("S1", *_CONDITION_RULES[(mode, kind)]))


def _subtree(node: FlowNode) -> Iterator[FlowNode]:
    yield node
    for child in node.children:
        yield from _subtree(child)


def _condition(case: FlowNode, mode: DecisionMode) -> CaseCondition:
    label = case.label
    if case.is_default_case:
        return CaseCondition(ConditionKind.DEFAULT, "$default")
    if label is None:
        kind = ConditionKind.UNLABELLED if mode is DecisionMode.EXPRESSIONS else ConditionKind.EMPTY
        return CaseCondition(kind)
    if label.disclosure is not TextDisclosure.INCLUDED or label.value is None:
        return CaseCondition(ConditionKind.WITHHELD)
    text = label.value
    if mode is DecisionMode.EXPRESSIONS:
        refs = expression_refs(text)
        return CaseCondition(
            ConditionKind.EXPRESSION, text, refs or (), refs_parsed=refs is not None
        )
    if text == "$null":
        return CaseCondition(ConditionKind.NULL, text)
    if len(text) > 2 and text.startswith("/") and text.endswith("/"):
        return CaseCondition(ConditionKind.PATTERN, text)
    return CaseCondition(ConditionKind.VALUE, text)


def _form(node: FlowNode) -> str | None:
    if node.type is not FlowNodeType.SEQUENCE:
        return None
    form = (node.form or "").strip().upper()
    return form if form in FORMS else None


def _exit_on(node: FlowNode) -> str:
    return (node.exit_on or "FAILURE").strip().upper() if node.type is FlowNodeType.SEQUENCE else ""


def _is_alternatives(node: FlowNode) -> bool:
    """An EXIT-ON SUCCESS sequence (TRY/CATCH blocks inside it are its alternatives)."""
    return node.type is FlowNodeType.SEQUENCE and not _form(node) and _exit_on(node) == "SUCCESS"


def _handles_failure_of(parent: FlowNode, child: FlowNode) -> bool:
    """True when `parent` keeps going after `child` fails (S10, S13).

    An EXIT-ON DONE sequence always does. An EXIT-ON SUCCESS sequence does only when a later
    alternative (not FINALLY) can still run. A TRY block is handled by the CATCH block right after
    it; a failing CATCH, or a step without a CATCH after it, passes the failure on.
    """
    siblings = list(parent.children)
    position = next(index for index, item in enumerate(siblings) if item is child)
    later = siblings[position + 1 :]
    if parent.type is FlowNodeType.SEQUENCE and not _form(parent):
        if _exit_on(parent) == "DONE":
            return True
        if _exit_on(parent) == "SUCCESS":
            return any(_form(item) != "FINALLY" for item in later)
    return _form(child) == "TRY" and bool(later) and _form(later[0]) == "CATCH"


def _parent_is_case(parent: FlowNode | None) -> bool:
    return parent is not None and parent.type is FlowNodeType.BRANCH_CASE


def _is_significant(node: FlowNode) -> bool:
    if node.type in (FlowNodeType.BRANCH, FlowNodeType.EXIT):
        return True
    if node.type is FlowNodeType.SEQUENCE:
        return bool(_form(node)) or _exit_on(node) != "FAILURE"
    return False


def _reach(guard: Guard, blocked: bool) -> Reach:
    if blocked:
        return Reach.UNREACHABLE
    kinds = {term.kind for term in guard.terms}
    if GuardKind.ON_FAILURE_OF in kinds:
        return Reach.FAILURE_PATH
    return Reach.CONDITIONAL if kinds else Reach.NORMAL
