"""Scenarios: the combinations of decision outcomes a FLOW service can take, along chains of
decisions whose fields depend on earlier decisions.

Derived facts, computed on demand from the control model (`flow_logic`) and the origins of the
decision fields (`flow_lineage`), never stored in `analysis.json`. Nothing is evaluated.

- A decision depends on an earlier one when an origin of a field it tests (or of a field copied
  into it) runs only in some cases of the earlier decision, or when its field may carry what a
  call in such a case returns. Decisions inside a LOOP or REPEAT take a case per iteration, so
  they are never combined.
- Decisions are combined only along these dependencies: one table per chain, at most
  MAX_CHAIN decisions long. Independent decisions are never multiplied with each other.
- Each scenario takes one outcome per decision: a case, "no case matches" (S7), a failure
  because the switch variable is missing (S31), or "not reached". The origins of the later
  decisions are recomputed for the outcomes chosen so far (a lineage walk with those choices
  fixed), so cases that leave the same origins further on are grouped.
- A decision that some paths of the chosen outcomes do not reach (its guard has conditions
  the chosen outcomes do not settle) also gets "not reached".
- An outcome is ruled out only when that is provable: the field has one observed definition,
  a literal the policy includes and without surrounding blanks, on every path, and a value
  label differs from it (S2). A match never rules out "no case matches" or `$default`: the
  parsed labels are trimmed, so an exact match is not certain. Patterns, expressions, withheld
  labels and literals the policy hides are never used to rule anything out.
- Every scenario names the rules it rests on; assumed ones reach the page as assumptions.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from wm_doc.flow_lineage import (
    Choice,
    FlowLineage,
    Origin,
    OriginKind,
    VariableOrigins,
    compute_flow_lineage,
)
from wm_doc.flow_logic import (
    ConditionKind,
    Decision,
    DecisionMode,
    FlowLogic,
    Guard,
    GuardKind,
    Reach,
    sort_rules,
    subtree,
)
from wm_doc.flow_paths import path_ref
from wm_doc.ir import FlowNode, FlowNodeType, FlowService, ServiceSignature

MAX_CHAIN = 4  # decisions combined in one table
MAX_SCENARIOS = 32  # scenarios per table
MAX_TABLES = 10  # tables per service
MAX_WALKS = 128  # lineage walks per service
MAX_PATHS = 200  # dependency paths looked at before the tables are chosen

# Origins that bring a value from outside the service's own definitions.
_OUTSIDE = frozenset(
    {
        OriginKind.CALLER,
        OriginKind.SERVICE_INPUT,
        OriginKind.CALL_RESPONSE,
        OriginKind.TRANSFORMER,
        OriginKind.RESTORED,
    }
)
_UNFOLLOWED_NOTES = frozenset({"scope", "too_deep", "not_followed"})
_UNREADABLE_NOTES = frozenset({"NO_SWITCH", "LABELS_WITHHELD", "EXPRESSION_NOT_SPLIT"})


class OutcomeKind(StrEnum):
    CASE = "case"  # one of the listed cases runs (with no_match: or none matches)
    NO_MATCH = "no_match"  # no case matches and there is no $default (S7)
    FAILS = "fails"  # the switch variable is missing (S31)
    NOT_REACHED = "not_reached"


class Feasibility(StrEnum):
    POSSIBLE = "possible"  # values this service sets itself may lead here
    CONDITIONAL = "conditional"  # it also needs a value from the caller or a call's response
    UNRESOLVED = "unresolved"  # a field or condition is not followed, so it cannot be told


@dataclass(frozen=True, slots=True)
class Outcome:
    decision_id: str
    kind: OutcomeKind
    case_ids: tuple[str, ...] = ()
    no_match: bool = False

    @property
    def grouped(self) -> bool:
        return len(self.case_ids) + int(self.no_match) > 1

    def choice(self) -> Choice:
        return Choice(frozenset(self.case_ids), self.no_match, self.kind is OutcomeKind.FAILS)


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str  # P1, P2, ... per service
    outcomes: tuple[Outcome, ...]  # one per decision of the table, in order
    call_ids: tuple[str, ...]  # calls these outcomes decide, in order
    ends: tuple[str, ...]  # EXITs every path of the last outcome ends with
    fails_at: str | None  # the decision whose missing switch fails it (S31)
    failure_end: str | None  # the step whose failure is handled; None when unknown
    service_fails: bool  # that failure is handled nowhere: the service fails
    # (LOOP node id, IN-ARRAY) for LOOPs on its paths that fail on a missing array (S29)
    loop_failures: tuple[tuple[str, str | None], ...]
    depends_on_calls: tuple[str, ...]
    feasibility: Feasibility
    rules: tuple[str, ...]
    after: str | None  # the last decision reached


@dataclass(frozen=True, slots=True)
class RuledOut:
    prefix: tuple[Outcome, ...]  # the outcomes of the earlier decisions
    decision_id: str
    case_id: str | None  # None: "no case matches"
    value: str  # the literal the field always has there
    path: str  # the field, as written
    node_id: str | None  # the step that sets it


@dataclass(frozen=True, slots=True)
class ScenarioTable:
    decision_ids: tuple[str, ...]
    left_out: tuple[str, ...]  # later decisions that depend on these but are not combined
    scenarios: tuple[Scenario, ...]
    ruled_out: tuple[RuledOut, ...]
    truncated: bool  # more combinations than are listed
    walk_limit: bool = False  # cut short because MAX_WALKS walks were used up


@dataclass(frozen=True)
class FlowScenarios:
    service: str
    tables: tuple[ScenarioTable, ...]
    dependencies: tuple[tuple[str, str], ...]  # (earlier decision, decision that depends on it)
    independent: tuple[str, ...]  # decisions combined with no other one
    in_loops: tuple[str, ...]  # decisions inside a LOOP or REPEAT, never combined
    limits: tuple[str, ...]


def compute_flow_scenarios(
    service: FlowService,
    logic: FlowLogic | None,
    lineage: FlowLineage | None,
    signatures: Mapping[str, ServiceSignature] | None = None,
) -> FlowScenarios | None:
    """Scenarios of a FLOW service's decisions; None when it has no decisions."""
    if service.flow_tree is None or logic is None or lineage is None or not logic.decisions:
        return None
    return _Scenarios(service, service.flow_tree, logic, lineage, signatures or {}).run()


# --- implementation ------------------------------------------------------------------------


def _named(guard: Guard) -> set[str]:
    """Decisions a guard names through cases taken or not taken."""
    return {
        term.decision_id
        for term in guard.terms
        if term.decision_id and term.kind in (GuardKind.IN_CASE, GuardKind.NOT_CASES)
    }


def _closure(lineage: FlowLineage, origin_ids: Iterable[str]) -> list[Origin]:
    """The origins and, through copies, the origins of the fields they copy."""
    seen: dict[str, Origin] = {}
    stack = list(origin_ids)
    while stack:
        origin_id = stack.pop()
        if origin_id in seen:
            continue
        origin = lineage.origin(origin_id)
        seen[origin_id] = origin
        stack.extend(origin.source_origins)
    return [seen[key] for key in sorted(seen, key=lambda item: int(item[1:]))]


def _identity(origin: Origin) -> tuple[object, ...]:
    """What an origin is, independent of the numbering of one walk."""
    return (
        origin.kind,
        origin.node_id,
        origin.path.text(),
        origin.written_path.text() if origin.written_path else None,
        origin.source_path.text() if origin.source_path else None,
        origin.value,
        origin.call_id,
    )


class _Scenarios:
    def __init__(
        self,
        service: FlowService,
        root: FlowNode,
        logic: FlowLogic,
        lineage: FlowLineage,
        signatures: Mapping[str, ServiceSignature],
    ) -> None:
        self.service = service
        self.root = root
        self.logic = logic
        self.lineage = lineage
        self.signatures = signatures
        self.index = {decision.id: position for position, decision in enumerate(logic.decisions)}
        self.loops = [node for node in subtree(root) if node.type is FlowNodeType.LOOP]
        self.position: dict[str, int] = {}
        self.parent: dict[str, str | None] = {}
        stack: list[tuple[FlowNode, str | None]] = [(root, None)]
        while stack:
            node, parent = stack.pop()
            self.position[node.id] = len(self.position)
            self.parent[node.id] = parent
            stack.extend((child, node.id) for child in reversed(node.children))
        # Steps that may fail on a missing value and so skip what follows: LOOPs over an
        # IN-ARRAY (S29) and BRANCHes whose missing switch fails them (S31).
        self.may_fail = [node.id for node in self.loops] + [
            decision.node_id for decision in logic.decisions if decision.missing_fails
        ]
        self.walks = 0
        self.followed: frozenset[str] = frozenset()  # decisions of every table
        self.cache: dict[tuple[object, ...], FlowLineage | None] = {}
        self.limits: list[str] = []
        self.scenario_count = 0

    def run(self) -> FlowScenarios:
        in_loops = tuple(item.id for item in self.logic.decisions if item.loop_id is not None)
        deps = self._dependencies(set(in_loops))
        dependencies = tuple(
            sorted(
                ((earlier, later) for later, items in deps.items() for earlier in items),
                key=lambda pair: (self.index[pair[1]], self.index[pair[0]]),
            )
        )
        paths = self._paths(deps)
        # One walk serves every table: it follows the decisions of all of them.
        self.followed = frozenset(item for path, _left in paths for item in path)
        tables = tuple(self._table(path, left_out) for path, left_out in paths)
        combined = {decision for table in tables for decision in table.decision_ids}
        independent = tuple(
            item.id
            for item in self.logic.decisions
            if item.id not in combined and item.id not in in_loops
        )
        return FlowScenarios(
            service=self.service.identity.full_name,
            tables=tables,
            dependencies=dependencies,
            independent=independent,
            in_loops=in_loops,
            limits=tuple(dict.fromkeys(self.limits)),
        )

    # dependencies -------------------------------------------------------------------------

    def _dependencies(self, excluded: set[str]) -> dict[str, set[str]]:
        deps: dict[str, set[str]] = {}
        for decision in self.logic.decisions:
            if decision.id in excluded:
                continue
            found: set[str] = set()
            for variable in self.lineage.for_decision(decision.id):
                for origin in _closure(self.lineage, variable.origins):
                    found |= _named(origin.guard)
                for call_id in variable.depends_on_calls:
                    found |= _named(self.logic.call(call_id).guard)
            deps[decision.id] = {
                item
                for item in found
                if item not in excluded
                and item != decision.id
                and self.index[item] < self.index[decision.id]
            }
        return deps

    def _paths(self, deps: dict[str, set[str]]) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
        dependents: dict[str, list[str]] = {}
        for later, items in deps.items():
            for earlier in items:
                dependents.setdefault(earlier, []).append(later)
        for followers in dependents.values():
            followers.sort(key=self.index.__getitem__)
        roots = [
            decision.id
            for decision in self.logic.decisions
            if decision.id in deps and not deps[decision.id] and dependents.get(decision.id)
        ]
        found: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
        limited = False

        def further(start: str, path: tuple[str, ...]) -> tuple[str, ...]:
            seen: set[str] = set()
            stack = [start]
            while stack:
                for item in dependents.get(stack.pop(), ()):
                    if item not in seen and item not in path:
                        seen.add(item)
                        stack.append(item)
            return tuple(sorted(seen, key=self.index.__getitem__))

        def extend(path: tuple[str, ...]) -> None:
            nonlocal limited
            if len(found) >= MAX_PATHS:
                limited = True
                return
            nexts = [item for item in dependents.get(path[-1], ()) if item not in path]
            if not nexts:
                found.append((path, ()))
            elif len(path) >= MAX_CHAIN:
                found.append((path, further(path[-1], path)))
            else:
                for item in nexts:
                    extend((*path, item))

        for root in roots:
            extend((root,))
        # A chain whose decisions all belong to a longer one adds nothing.
        kept: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
        for path, left_out in found:
            members = set(path)
            if any(members < set(other) for other, _left in found):
                continue
            if any(members == set(other) for other, _left in kept):
                continue
            kept.append((path, left_out))
        if len(kept) > MAX_TABLES:
            limited = True
            kept = kept[:MAX_TABLES]
        if limited:
            self.limits.append(f"at most {MAX_TABLES} chains of decisions are combined")
        return kept

    # walks ---------------------------------------------------------------------------------

    def _walk(self, outcomes: tuple[Outcome, ...]) -> FlowLineage | None:
        chosen = tuple(
            sorted(
                (item for item in outcomes if item.kind is not OutcomeKind.NOT_REACHED),
                key=lambda item: self.index[item.decision_id],
            )
        )
        key = (chosen,)
        if key in self.cache:
            return self.cache[key]
        if self.walks >= MAX_WALKS:
            self.limits.append(f"at most {MAX_WALKS} combinations are followed per service")
            return None
        self.walks += 1
        choices = {item.decision_id: item.choice() for item in chosen}
        # A decision that is reached sits in the cases its guard names: those cases are taken.
        implied: dict[str, set[str]] = {}
        for item in chosen:
            for term in self.logic.decision(item.decision_id).guard.terms:
                other = term.decision_id
                if term.kind is not GuardKind.IN_CASE or other is None or other in choices:
                    continue
                if self.logic.decision(other).loop_id is not None:
                    continue
                cases = set(term.case_ids)
                implied[other] = implied[other] & cases if other in implied else cases
        for other, cases in implied.items():
            choices[other] = Choice(frozenset(cases))
        result = compute_flow_lineage(
            self.service, self.logic, self.signatures, only=self.followed, choices=choices
        )
        self.cache[key] = result
        return result

    # tables --------------------------------------------------------------------------------

    def _table(self, path: tuple[str, ...], left_out: tuple[str, ...]) -> ScenarioTable:
        leaves: list[tuple[tuple[Outcome, ...], FlowLineage]] = []
        ruled: list[RuledOut] = []
        truncated = False
        limited = False

        def visit(position: int, outcomes: tuple[Outcome, ...], walk: FlowLineage) -> None:
            nonlocal truncated, limited
            if truncated:
                return
            if position == len(path):
                if len(leaves) >= MAX_SCENARIOS:
                    truncated = True
                    return
                leaves.append((outcomes, walk))
                return
            decision = self.logic.decision(path[position])
            missing = Outcome(decision.id, OutcomeKind.NOT_REACHED)
            if decision.node_id not in walk.reached_nodes or self._skipped(decision, outcomes):
                visit(position + 1, (*outcomes, missing), walk)
                return
            options = self._options(decision, walk, outcomes, ruled)
            if self._bypassable(decision, outcomes, walk):
                options.append(missing)
            later = path[position + 1 :]
            groups: list[Outcome] = []
            runs: list[FlowLineage | None] = []
            signatures: dict[tuple[object, ...], int] = {}
            for option in options:
                if option.kind is OutcomeKind.NOT_REACHED:
                    groups.append(option)
                    runs.append(walk)
                    continue
                run = self._walk((*outcomes, option))
                if run is None:
                    truncated = limited = True
                    return
                if later and option.kind in (OutcomeKind.CASE, OutcomeKind.NO_MATCH):
                    signature = (self._ends(option), self._signature(later, run))
                    if signature in signatures:
                        slot = signatures[signature]
                        groups[slot] = self._merge(groups[slot], option)
                        runs[slot] = None
                        continue
                    signatures[signature] = len(groups)
                groups.append(option)
                runs.append(run)
            for option, run in zip(groups, runs, strict=True):
                if run is None:
                    run = self._walk((*outcomes, option))
                    if run is None:
                        truncated = limited = True
                        return
                visit(position + 1, (*outcomes, option), run)

        initial = self._walk(())
        if initial is None:
            truncated = limited = True
        else:
            visit(0, (), initial)
        scenarios = tuple(self._scenario(path, outcomes, walk) for outcomes, walk in leaves)
        return ScenarioTable(
            decision_ids=path,
            left_out=left_out,
            scenarios=scenarios,
            ruled_out=tuple(dict.fromkeys(ruled)),
            truncated=truncated,
            walk_limit=limited,
        )

    def _skipped(self, decision: Decision, outcomes: tuple[Outcome, ...]) -> bool:
        """True when the decision sits in a case of an earlier decision that is not reached."""
        settled = {item.decision_id: item for item in outcomes}
        return any(
            term.kind is GuardKind.IN_CASE
            and term.decision_id in settled
            and settled[term.decision_id].kind is OutcomeKind.NOT_REACHED
            for term in decision.guard.terms
        )

    def _bypassable(
        self, decision: Decision, outcomes: tuple[Outcome, ...], walk: FlowLineage
    ) -> bool:
        """True when some path of the chosen outcomes may pass the decision by.

        Conditions on the outcomes already chosen are settled by the walk; any other condition
        of its guard (a failure, an earlier EXIT, a decision outside the table) may not hold.
        An earlier step that fails on a missing value (S29, S31) may also skip it.
        """
        settled = {
            item.decision_id for item in outcomes if item.kind is not OutcomeKind.NOT_REACHED
        }
        if any(
            not (
                term.kind in (GuardKind.IN_CASE, GuardKind.NOT_CASES)
                and term.decision_id in settled
            )
            for term in decision.guard.terms
        ):
            return True
        chosen = {
            self.logic.decision(item).node_id for item in settled
        }  # their failures are chosen outcomes already
        target = decision.node_id
        for node_id in self.may_fail:
            if node_id in chosen or node_id not in walk.reached_nodes:
                continue
            if self.position[node_id] >= self.position[target] or self._inside(target, node_id):
                continue
            end = self.logic.failure_ends.get(node_id, (None, ()))[0]
            if end is None or end == self.root.id or self._inside(target, end):
                return True
        return False

    def _inside(self, node_id: str, ancestor: str) -> bool:
        current = self.parent.get(node_id)
        while current is not None:
            if current == ancestor:
                return True
            current = self.parent.get(current)
        return False

    def _consistent(self, guard: Guard, outcomes: tuple[Outcome, ...]) -> bool:
        """False when the guard needs a case of a decision that the outcomes exclude."""
        settled = {item.decision_id: item for item in outcomes}
        for term in guard.terms:
            outcome = settled.get(term.decision_id or "")
            if outcome is None:
                continue
            taken = set(outcome.case_ids)
            if term.kind is GuardKind.IN_CASE:
                if outcome.kind in (OutcomeKind.NOT_REACHED, OutcomeKind.FAILS):
                    return False
                if not taken & set(term.case_ids):
                    return False
            elif term.kind is GuardKind.NOT_CASES:
                if taken and not outcome.no_match and taken <= set(term.case_ids):
                    return False
        return True

    def _options(
        self,
        decision: Decision,
        walk: FlowLineage,
        prefix: tuple[Outcome, ...],
        ruled: list[RuledOut],
    ) -> list[Outcome]:
        """The outcomes this decision may have after `prefix`, in case order."""
        variables = walk.for_decision(decision.id)
        literal = self._literal(decision, walk, variables)
        live = [item for item in decision.cases if item.unreachable_rule is None]
        value, origin = literal if literal is not None else (None, None)

        def rule_out(case_id: str | None) -> None:
            assert value is not None and origin is not None
            ruled.append(
                RuledOut(prefix, decision.id, case_id, value, origin.path.text(), origin.node_id)
            )

        options: list[Outcome] = []
        for item in live:
            kind = item.condition.kind
            if value is not None and kind is ConditionKind.VALUE and item.condition.text != value:
                rule_out(item.id)
                continue
            options.append(Outcome(decision.id, OutcomeKind.CASE, (item.id,)))
        if decision.falls_through:
            options.append(Outcome(decision.id, OutcomeKind.NO_MATCH, (), True))
        if decision.missing_fails and self._may_be_missing(variables):
            options.append(Outcome(decision.id, OutcomeKind.FAILS))
        return options

    def _literal(
        self, decision: Decision, walk: FlowLineage, variables: tuple[VariableOrigins, ...]
    ) -> tuple[str, Origin] | None:
        """The literal the switch field has on every path, when that is certain."""
        if decision.mode is not DecisionMode.SWITCH or len(variables) != 1:
            return None
        variable = variables[0]
        if not variable.unique or variable.notes:
            return None
        origin = walk.origin(variable.origins[0])
        if (
            origin.kind is not OriginKind.SET
            or origin.value is None
            or origin.template
            or origin.written_path is not None
            or origin.notes
            or origin.value != origin.value.strip()  # labels are trimmed when parsed
        ):
            return None
        return origin.value, origin

    def _may_be_missing(self, variables: tuple[VariableOrigins, ...]) -> bool:
        if not variables:
            return True
        # A call in between may drop the field too (S16).
        return any(
            item.absent_possible or item.notes or item.calls_in_between for item in variables
        )

    def _ends(self, outcome: Outcome) -> tuple[str, ...]:
        """The EXITs every path of the outcome ends with, when it has no other way on."""
        if outcome.kind is not OutcomeKind.CASE or outcome.no_match:
            return ()
        branch = self.logic.decision(outcome.decision_id).node_id
        found: dict[str, None] = {}
        for case_id in outcome.case_ids:
            # An EXIT that leaves only the BRANCH lets the flow go on after it.
            leaving = [
                exit_id
                for exit_id in self.logic.case(case_id).ends_with
                if self.logic.exit(exit_id).reach_id != branch
            ]
            if not leaving:
                return ()
            found.update(dict.fromkeys(leaving))
        return tuple(sorted(found, key=lambda exit_id: int(exit_id[1:])))

    def _signature(self, later: tuple[str, ...], walk: FlowLineage) -> tuple[object, ...]:
        """What the later decisions see after an outcome: reached, and their origins."""
        parts: list[object] = []
        for decision_id in later:
            reached = self.logic.decision(decision_id).node_id in walk.reached_nodes
            fields = tuple(
                (
                    variable.path.text(),
                    frozenset(_identity(origin) for origin in _closure(walk, variable.origins)),
                    variable.depends_on_calls,
                )
                for variable in walk.for_decision(decision_id)
            )
            parts.append((decision_id, reached, fields if reached else ()))
        return tuple(parts)

    def _merge(self, first: Outcome, second: Outcome) -> Outcome:
        cases = sorted(
            {*first.case_ids, *second.case_ids}, key=lambda case_id: self.logic.case(case_id).index
        )
        return Outcome(
            first.decision_id,
            OutcomeKind.CASE if cases else OutcomeKind.NO_MATCH,
            tuple(cases),
            first.no_match or second.no_match,
        )

    # scenarios -----------------------------------------------------------------------------

    def _scenario(
        self, path: tuple[str, ...], outcomes: tuple[Outcome, ...], walk: FlowLineage
    ) -> Scenario:
        self.scenario_count += 1
        members = set(path)
        reached = [item for item in outcomes if item.kind is not OutcomeKind.NOT_REACHED]
        last = reached[-1] if reached else None
        rules: set[str] = set()
        ends: tuple[str, ...] = ()
        fails_at: str | None = None
        failure_end: str | None = None
        for outcome in reached:
            if outcome.kind is OutcomeKind.FAILS:
                node_id = self.logic.decision(outcome.decision_id).node_id
                rules.update(self.logic.failure_ends.get(node_id, (None, ()))[1])
        if last is not None and last.kind is OutcomeKind.FAILS:
            fails_at = last.decision_id
            node_id = self.logic.decision(fails_at).node_id
            failure_end = self.logic.failure_ends.get(node_id, (None, ()))[0]
        elif last is not None:
            ends = self._ends(last)
        for exit_id in ends:
            effect = self.logic.exit(exit_id)
            rules.update(effect.rules)
            if "S33" in effect.rules:
                rules.add("S14")  # read through TRY, CATCH and FINALLY blocks
        calls = tuple(
            call.id
            for call in self.logic.calls
            if call.node_id in walk.reached_nodes
            and call.reach is not Reach.UNREACHABLE
            and _named(call.guard) & members
            and self._consistent(call.guard, outcomes)
        )
        for call_id in calls:
            rules.update(self.logic.call(call_id).guard.rules)
        loop_failures = tuple(
            (node.id, ref.text() if (ref := path_ref(node.in_array)) is not None else None)
            for node in self.loops
            if node.id in walk.reached_nodes
            and _named(self.logic.guard_of(node.id)) & members
            and self._consistent(self.logic.guard_of(node.id), outcomes)
        )
        if loop_failures:
            rules.add("S29")
        depends: dict[str, None] = {}
        unresolved = False
        conditional = False
        for outcome in reached:
            decision = self.logic.decision(outcome.decision_id)
            variables = walk.for_decision(decision.id)
            rules.update(self._outcome_rules(decision, outcome))
            rules.update(decision.guard.rules)  # how it is reached
            if not variables or set(decision.notes) & _UNREADABLE_NOTES:
                unresolved = True
            if any(
                self.logic.case(case_id).condition.kind is ConditionKind.WITHHELD
                for case_id in outcome.case_ids
            ):
                unresolved = True
            for variable in variables:
                if set(variable.notes) & _UNFOLLOWED_NOTES:
                    unresolved = True
                if variable.depends_on_calls or variable.calls_in_between:
                    conditional = True
                depends.update(dict.fromkeys(variable.depends_on_calls))
                for origin in _closure(walk, variable.origins):
                    rules.update(origin.rules)
                    rules.update(origin.guard.rules)
                    if origin.kind is OriginKind.UNKNOWN:
                        unresolved = True
                    elif origin.kind in _OUTSIDE:
                        conditional = True
        if unresolved:
            feasibility = Feasibility.UNRESOLVED
        elif conditional:
            feasibility = Feasibility.CONDITIONAL
        else:
            feasibility = Feasibility.POSSIBLE
        return Scenario(
            id=f"P{self.scenario_count}",
            outcomes=outcomes,
            call_ids=calls,
            ends=ends,
            fails_at=fails_at,
            failure_end=failure_end,
            service_fails=failure_end is not None and failure_end == self.root.id,
            loop_failures=loop_failures,
            depends_on_calls=tuple(sorted(depends, key=lambda call_id: int(call_id[1:]))),
            feasibility=feasibility,
            rules=sort_rules(rules),
            after=last.decision_id if last is not None else None,
        )

    def _outcome_rules(self, decision: Decision, outcome: Outcome) -> set[str]:
        rules: set[str] = set()
        for case_id in outcome.case_ids:
            rules.update(self.logic.case(case_id).rules)
        if outcome.no_match:
            rules.add("S7")
        if outcome.kind is OutcomeKind.FAILS:
            rules.add("S31")
        # Cases that never run are left out; that rests on why they never run.
        rules.update(item.unreachable_rule for item in decision.cases if item.unreachable_rule)
        return rules
