"""Decision inputs and what callers pass into them: conservative facts across services.

Stage 7 of the conditional-flow work. A decision input is a field a decision tests that this
service does not set before the decision on some path, so its value comes from the caller's
pipeline (S16). For each direct caller (an analysed FLOW service, at most MAX_CALLERS) the
caller's own lineage is walked with a probe on that field just before every call to this
service, after the call's input map: the caller sets it to one literal, sets or copies it
otherwise, or does not set it before the call (it passes through from its own caller).

Only one conclusion is drawn, and only when everything about it is observed: the caller sets
one literal (shown as the literal policy allows, without surrounding blanks) that reaches the
call on every path, nothing runs in between that may change it (`flow_writes` proves a call
cannot), and this service never sets the field before a decision that compares it in switch
mode, outside a loop, with value, empty, `$null` or `$default` cases only. Then the first case
whose label equals the value runs, or `$default`, or none (S1, S2, S6, S7). Patterns,
expressions, withheld labels and loops never lead to a conclusion. Nothing is matched by
similar names: fields are the same pipeline path. Derived on demand, never stored in
`analysis.json`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from wm_doc.flow_lineage import (
    FlowLineage,
    Key,
    MapRole,
    Origin,
    OriginKind,
    VariableOrigins,
    compute_flow_lineage,
)
from wm_doc.flow_logic import (
    Certainty,
    ConditionKind,
    Decision,
    DecisionMode,
    FlowLogic,
    compute_flow_logic,
    sort_rules,
    weakest,
)
from wm_doc.flow_paths import PipelineRef
from wm_doc.flow_writes import PipelineWrites, compute_pipeline_writes
from wm_doc.ir import CallType, FlowService, ServiceSignature

__all__ = [
    "MAX_CALLERS",
    "CallerPass",
    "DecisionInput",
    "PassKind",
    "PipelineWrites",
    "compute_decision_inputs",
    "compute_pipeline_writes",
]

MAX_CALLERS = 50
_FROM_CALLER = (OriginKind.CALLER, OriginKind.SERVICE_INPUT)
_CONCLUSIVE = (ConditionKind.VALUE, ConditionKind.EMPTY, ConditionKind.NULL, ConditionKind.DEFAULT)


class PassKind(StrEnum):
    VALUE = "value"  # the caller sets it to one literal
    SET_OR_COPY = "set_or_copy"  # the caller sets or copies it some other way
    THROUGH = "through"  # the caller does not set it before the call
    UNKNOWN = "unknown"  # not read: a caller that is not a FLOW service, or a call not reached


@dataclass(frozen=True)
class CallerPass:
    """What one call of one caller passes into a decision input."""

    caller: str
    call_id: str  # in the caller ("" when not read)
    path: PipelineRef
    kind: PassKind
    value: str | None  # VALUE: the literal, as the literal policy allows
    origins: tuple[Origin, ...]  # in the caller, document order
    calls_between: tuple[str, ...]  # calls in the caller that may change it first
    more_calls_between: bool
    # Decision id -> the only cases that can run on this call (() when none runs); None when
    # nothing is concluded.
    cases: dict[str, tuple[str, ...]] | None
    certainty: Certainty
    rules: tuple[str, ...]
    caller_logic: FlowLogic | None  # to name the caller's steps


@dataclass(frozen=True)
class DecisionInput:
    path: PipelineRef
    decision_ids: tuple[str, ...]
    declared: bool  # a declared input of the service
    passes: tuple[CallerPass, ...]
    callers_hidden: int  # direct callers beyond MAX_CALLERS, not read


def compute_decision_inputs(
    service: FlowService,
    logic: FlowLogic | None,
    lineage: FlowLineage | None,
    *,
    callers: Iterable[FlowService],
    signatures: Mapping[str, ServiceSignature],
    writes: Mapping[str, PipelineWrites],
) -> tuple[DecisionInput, ...]:
    """The decision inputs of `service` and what its direct `callers` pass into them."""
    if logic is None or lineage is None:
        return ()
    by_path: dict[Key, list[VariableOrigins]] = {}
    for variable in lineage.variables:
        origins = [lineage.origin(origin_id) for origin_id in variable.origins]
        if variable.reached and any(origin.kind in _FROM_CALLER for origin in origins):
            by_path.setdefault(variable.path.base(), []).append(variable)
    if not by_path:
        return ()
    name = service.identity.full_name
    unique = {item.identity.full_name: item for item in callers if item.identity.full_name != name}
    others = sorted(
        unique.values(),
        key=lambda item: (item.identity.full_name.casefold(), item.identity.full_name),
    )
    read = others[:MAX_CALLERS]
    passes: dict[Key, list[CallerPass]] = {key: [] for key in by_path}
    for caller in read:
        for item in _passes(caller, name, tuple(by_path), signatures, writes):
            conclusion = _conclusion(item, by_path[item.path.base()], logic, lineage)
            passes[item.path.base()].append(conclusion)
    return tuple(
        DecisionInput(
            path=PipelineRef(key),
            decision_ids=tuple(dict.fromkeys(variable.decision_id for variable in variables)),
            declared=any(
                lineage.origin(origin_id).kind is OriginKind.SERVICE_INPUT
                for variable in variables
                for origin_id in variable.origins
            ),
            passes=tuple(passes[key]),
            callers_hidden=len(others) - len(read),
        )
        for key, variables in by_path.items()
    )


def _passes(
    caller: FlowService,
    target: str,
    keys: Sequence[Key],
    signatures: Mapping[str, ServiceSignature],
    writes: Mapping[str, PipelineWrites],
) -> list[CallerPass]:
    caller_name = caller.identity.full_name
    logic = compute_flow_logic(caller)
    lineage = (
        compute_flow_lineage(
            caller, logic, signatures, only=(), writes=writes, probes={target: keys}
        )
        if logic is not None
        else None
    )
    if logic is None or lineage is None:
        return [_unread(caller_name, PipelineRef(key)) for key in keys]
    found: list[CallerPass] = []
    for probe in lineage.probes:
        origins = tuple(lineage.origin(origin_id) for origin_id in probe.origins)
        kind, value = _kind(origins, probe.call_id)
        # What this call's own input map sets is what the service receives; S17 is only
        # about whether it stays in the pipeline after the call.
        own_input = [origin for origin in origins if _own_input(origin, probe.call_id)]
        rules = [
            rule
            for item in origins
            for rule in item.rules
            if not (rule == "S17" and item in own_input)
        ]
        found.append(
            CallerPass(
                caller=caller_name,
                call_id=probe.call_id,
                path=probe.path,
                kind=kind,
                value=value,
                origins=origins,
                calls_between=probe.calls_in_between,
                more_calls_between=probe.more_calls_in_between,
                cases=None,
                certainty=(
                    Certainty.POSSIBLE
                    if kind is PassKind.THROUGH or probe.calls_in_between
                    else weakest(
                        Certainty.OBSERVED if origin in own_input else origin.certainty
                        for origin in origins
                    )
                ),
                rules=sort_rules(("S16", *rules)),
                caller_logic=logic,
            )
        )
    # A transformer gets only what its own input map gives it (S18): not read here.
    for call in logic.calls:
        if call.target == target and call.call_type is CallType.MAPINVOKE:
            found += [_unread(caller_name, PipelineRef(key), call.id) for key in keys]
    return found


def _unread(caller: str, path: PipelineRef, call_id: str = "") -> CallerPass:
    return CallerPass(
        caller=caller,
        call_id=call_id,
        path=path,
        kind=PassKind.UNKNOWN,
        value=None,
        origins=(),
        calls_between=(),
        more_calls_between=False,
        cases=None,
        certainty=Certainty.UNKNOWN,
        rules=(),
        caller_logic=None,
    )


def _own_input(origin: Origin, call_id: str) -> bool:
    return origin.map_role is MapRole.CALL_INPUT and origin.call_id == call_id


def _kind(origins: tuple[Origin, ...], call_id: str) -> tuple[PassKind, str | None]:
    if not origins:
        return PassKind.UNKNOWN, None
    if all(origin.kind in _FROM_CALLER for origin in origins):
        return PassKind.THROUGH, None
    if len(origins) == 1:
        origin = origins[0]
        observed = origin.certainty is Certainty.OBSERVED or _own_input(origin, call_id)
        # The only definition reaching the call, on every path, certainly writes this value.
        if (
            origin.kind is OriginKind.SET
            and origin.value is not None
            and not origin.template
            and origin.written_path is None
            and not origin.weak
            and observed
        ):
            return PassKind.VALUE, origin.value
    return PassKind.SET_OR_COPY, None


def _conclusion(
    item: CallerPass,
    variables: list[VariableOrigins],
    logic: FlowLogic,
    lineage: FlowLineage,
) -> CallerPass:
    """`item` with the only cases that can run on this call, when that is certain."""
    value = item.value
    if item.kind is not PassKind.VALUE or value is None or item.calls_between:
        return item
    if value != value.strip():
        return item  # labels are trimmed when parsed, so a match is not certain
    if value == "" and not any(
        case.condition.kind is ConditionKind.EMPTY
        for variable in variables
        for case in logic.decision(variable.decision_id).cases
    ):
        return item  # an empty value may also read as missing ($null): not certain
    cases: dict[str, tuple[str, ...]] = {}
    rules = set(item.rules) | {"S1", "S2"}
    for variable in variables:
        decision = logic.decision(variable.decision_id)
        if not _conclusive(variable, decision, lineage):
            continue
        live = [case for case in decision.cases if case.unreachable_rule is None]
        match = next(
            (
                case
                for case in live
                if (case.condition.kind is ConditionKind.VALUE and case.condition.text == value)
                or (case.condition.kind is ConditionKind.EMPTY and value == "")
            ),
            None,
        )
        if match is None:
            match = next(
                (case for case in live if case.condition.kind is ConditionKind.DEFAULT), None
            )
            rules.add("S6" if match is not None else "S7")
        cases[decision.id] = (match.id,) if match is not None else ()
    if not cases:
        return item
    return CallerPass(
        caller=item.caller,
        call_id=item.call_id,
        path=item.path,
        kind=item.kind,
        value=value,
        origins=item.origins,
        calls_between=item.calls_between,
        more_calls_between=item.more_calls_between,
        cases=cases,
        certainty=Certainty.DERIVED,
        rules=sort_rules(rules),
        caller_logic=item.caller_logic,
    )


def _conclusive(variable: VariableOrigins, decision: Decision, lineage: FlowLineage) -> bool:
    """Whether the caller's value alone decides `decision` (see the module docstring)."""
    if variable.calls_in_between or variable.notes or variable.loop_path is not None:
        return False
    if decision.loop_id is not None or decision.mode is not DecisionMode.SWITCH:
        return False
    switch = decision.switch
    if switch is None or switch.segments != variable.path.base():
        return False
    origins = [lineage.origin(origin_id) for origin_id in variable.origins]
    if not origins or any(origin.kind not in _FROM_CALLER for origin in origins):
        return False
    return all(
        case.condition.kind in _CONCLUSIVE and not case.condition.withheld
        for case in decision.cases
        if case.unreachable_rule is None
    )
