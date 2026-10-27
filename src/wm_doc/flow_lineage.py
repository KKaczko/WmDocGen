"""Where the values that a FLOW service's decisions test come from.

Derived facts, computed on demand from the parsed FLOW tree and the control model
(`flow_logic`), never stored in `analysis.json`. Starting from the fields the BRANCH steps test,
the analysis follows MAPCOPY sources backwards a bounded number of steps, then walks the FLOW
once in order and records, for every followed field, which definitions may reach each point:

- mapping lines (MAPSET, MAPCOPY, MAPDELETE) of MAP steps and of INVOKE input and output maps;
- outputs of transformers copied into the pipeline (a transformer sees only its own maps, S18);
- values a called service may leave: its declared outputs, and the fields its own output map
  reads (both possible, never replacing what was there);
- `pub.flow:clearPipeline` and `pub.flow:restorePipeline*` (S26, S27);
- the service's declared inputs, and otherwise the caller's pipeline.

Nothing is evaluated and no field is ever matched by a similar name. A definition replaces the
earlier ones only when it certainly writes the field; otherwise the earlier ones stay possible.
BRANCH cases, failure paths (CATCH, EXIT-ON SUCCESS and DONE, REPEAT), EXITs and LOOP iterations
are joined, so every definition that can reach a decision on a path the model knows is listed.
Any called service shares the pipeline (S16) and may change any field: calls between the last
certain definition and the decision are kept as a caveat rather than turned into definitions.
Steps with a scope, loops nested too deeply and steps nested too deeply are not followed; the
fields they may change get an "unknown" definition instead.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from wm_doc.flow_logic import (
    MAX_DEPTH,
    Certainty,
    ConditionKind,
    Decision,
    DecisionMode,
    FlowLogic,
    Guard,
    is_alternatives,
    sequence_exit_on,
    sort_rules,
    step_form,
    subtree,
    weakest,
)
from wm_doc.flow_paths import PipelineRef, path_ref
from wm_doc.flow_semantics import PIPELINE_RESET
from wm_doc.ir import (
    FlowMap,
    FlowNode,
    FlowNodeType,
    FlowService,
    LiteralDisclosure,
    MappingEndpoint,
    MappingOperation,
    MappingOperationType,
    ServiceSignature,
    SignatureField,
    SourceReference,
)

MAX_DECISIONS = 200  # decisions whose fields are followed
MAX_PATHS_PER_DECISION = 5  # fields of one decision (label expressions may test several)
MAX_TRACKED_PATHS = 200  # fields followed per service, copy sources included
MAX_COPY_CHAIN = 4  # MAPCOPY steps followed backwards from a decision field
MAX_PASSES = 4  # walks of a LOOP or REPEAT body before giving up on a stable state
MAX_LOOP_NESTING = 3  # deeper loops are walked once, with every field possibly changed
MAX_CALLS_KEPT = 5
MAX_TRANSFORMER_INPUTS = 5
MAX_DECLARED_DEPTH = 8

Key = tuple[str, ...]


class OriginKind(StrEnum):
    SET = "set"  # MAPSET
    COPY = "copy"  # MAPCOPY from another pipeline field
    TRANSFORMER = "transformer"  # MAPCOPY from a transformer's output
    CALL_RESPONSE = "call_response"  # a called service may leave it
    DROPPED = "dropped"  # MAPDELETE: absent afterwards
    CLEARED = "cleared"  # pub.flow:clearPipeline
    RESTORED = "restored"  # pub.flow:restorePipeline*
    PARTIAL = "partial"  # a mapping line writes or drops a field inside it
    COLLECTED = "collected"  # a LOOP's OUT-ARRAY
    SERVICE_INPUT = "service_input"  # a declared input, unchanged on this path
    CALLER = "caller"  # not set by this service on this path
    UNKNOWN = "unknown"  # changed by steps that are not followed


class MapRole(StrEnum):
    STEP = "step"  # a MAP step
    CALL_INPUT = "call_input"  # the input map of an INVOKE (written before the call, S17)
    CALL_OUTPUT = "call_output"  # the output map of an INVOKE
    TRANSFORMER_OUTPUT = "transformer_output"  # the output map of a transformer


# Origins after which the field may be absent.
ABSENT_KINDS = frozenset(
    {
        OriginKind.CALLER,
        OriginKind.SERVICE_INPUT,
        OriginKind.DROPPED,
        OriginKind.CLEARED,
        OriginKind.UNKNOWN,
    }
)


@dataclass(frozen=True, slots=True)
class Origin:
    """One way a field may have got its value before a decision tests it."""

    id: str  # O1, O2, ... in document order; inputs and the caller last
    kind: OriginKind
    path: PipelineRef  # the field it defines
    certainty: Certainty
    rules: tuple[str, ...]
    weak: bool  # earlier values may survive it
    node_id: str | None  # the step: MAP, INVOKE, transformer or LOOP; None for inputs
    call_id: str | None  # the call involved (its map, its response, a reset, a transformer)
    map_role: MapRole | None
    operation: MappingOperationType | None
    written_path: PipelineRef | None  # what the mapping line writes, when it is not `path`
    source_path: PipelineRef | None  # COPY: the field copied; TRANSFORMER: the output used
    source_origins: tuple[str, ...]  # COPY: the origins of the source when it was copied
    source_followed: bool  # False when the copied field was not followed (limits)
    value: str | None  # SET: the value, only when the literal policy includes it
    template: bool  # SET with variable substitution
    inputs: tuple[PipelineRef, ...]  # TRANSFORMER: pipeline fields mapped into it
    declared_path: PipelineRef | None  # SERVICE_INPUT, CALL_RESPONSE: the declared field
    notes: tuple[str, ...]  # why it is weak or possible (see the renderer)
    guard: Guard  # when the step runs
    line: int | None
    source: SourceReference | None


@dataclass(frozen=True, slots=True)
class VariableOrigins:
    """Where one field tested by a decision may come from, at the decision."""

    decision_id: str
    path: PipelineRef
    reached: bool  # False when no path the model knows reaches the decision
    origins: tuple[str, ...]  # origin ids, document order
    unique: bool  # exactly one certain definition, and no call in between
    absent_possible: bool
    calls_in_between: tuple[str, ...]  # the earliest MAX_CALLS_KEPT call ids
    more_calls_in_between: bool  # further calls run in between too
    depends_on_calls: tuple[str, ...]  # calls whose responses may feed the value
    loop_path: PipelineRef | None  # inside a LOOP over this array: its current element (S22)
    notes: tuple[str, ...]  # "scope", "too_deep", "not_followed", "list_element"


@dataclass(frozen=True)
class FlowLineage:
    service: str
    variables: tuple[VariableOrigins, ...]
    origins: tuple[Origin, ...]
    unfollowed: dict[str, tuple[str, ...]]  # decision id -> why some of its fields are not listed
    limits: tuple[str, ...]
    _origins: dict[str, Origin] = field(init=False, repr=False, compare=False)
    _by_decision: dict[str, tuple[VariableOrigins, ...]] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(self, "_origins", {item.id: item for item in self.origins})
        grouped: dict[str, list[VariableOrigins]] = {}
        for item in self.variables:
            grouped.setdefault(item.decision_id, []).append(item)
        object.__setattr__(
            self, "_by_decision", {key: tuple(value) for key, value in grouped.items()}
        )

    def origin(self, origin_id: str) -> Origin:
        """The origin with this id (O1, O2, ...)."""
        return self._origins[origin_id]

    def for_decision(self, decision_id: str) -> tuple[VariableOrigins, ...]:
        """The followed fields of one decision, in the order it tests them."""
        return self._by_decision.get(decision_id, ())


def compute_flow_lineage(
    service: FlowService,
    logic: FlowLogic | None,
    signatures: Mapping[str, ServiceSignature] | None = None,
) -> FlowLineage | None:
    """Origins of the fields tested by each decision; None without decisions.

    `signatures` maps analysed services to their signatures, so a call to one of them can
    name its declared outputs as possible origins.
    """
    if service.flow_tree is None or logic is None or not logic.decisions:
        return None
    return _Lineage(service, service.flow_tree, logic, signatures or {}).run()


# --- implementation ------------------------------------------------------------------------

# A field's state at one point: the definitions that may reach it (numbers of `_Def`s) and
# the calls run since the last definition that certainly wrote it: their indexes, sorted, only
# the earliest MAX_CALLS_KEPT + 1 (one more than is shown, to know there are more).
_Value = tuple[frozenset[int], tuple[int, ...]]
_State = dict[Key, _Value]


@dataclass(slots=True)
class _Result:
    normal: _State | None  # the step finished and the next one runs
    failed: _State | None  # states in which a failure may leave the step
    exits: list[tuple[str, _State]]  # EXIT node id, state, for EXITs going above the step


@dataclass(frozen=True, slots=True)
class _Write:
    op: MappingOperation
    kind: MappingOperationType
    target: Key
    indexed: bool  # the written path names one list element
    source: Key | None  # COPY: the pipeline source, or the transformer output field
    source_indexed: bool  # the copied path names one list element, which may be absent
    role: MapRole
    anchor: str  # the step whose guard applies
    call_node: str | None
    phase: int  # order within the INVOKE: input map, call, output map
    inputs: tuple[PipelineRef, ...] = ()


@dataclass(slots=True)
class _Def:
    number: int
    kind: OriginKind
    key: Key
    anchor: str | None
    phase: int
    order: int
    certainty: Certainty
    weak: bool
    rules: set[str] = field(default_factory=set)
    notes: set[str] = field(default_factory=set)
    call_node: str | None = None
    role: MapRole | None = None
    operation: MappingOperationType | None = None
    written: Key | None = None
    source_key: Key | None = None
    sources: set[int] = field(default_factory=set)
    followed: bool = True
    value: str | None = None
    template: bool = False
    inputs: tuple[PipelineRef, ...] = ()
    declared: Key | None = None
    line: int | None = None
    source: SourceReference | None = None


_KIND_RANK = {kind: rank for rank, kind in enumerate(OriginKind)}


class _Lineage:
    def __init__(
        self,
        service: FlowService,
        root: FlowNode,
        logic: FlowLogic,
        signatures: Mapping[str, ServiceSignature],
    ) -> None:
        self.service = service
        self.root = root
        self.logic = logic
        self.signatures = signatures
        self.nodes: dict[str, FlowNode] = {}
        self.parent: dict[str, FlowNode | None] = {}
        self.position: dict[str, int] = {}
        self._index(root, None)
        self.maps = {flow_map.structural_path: flow_map for flow_map in service.flow_maps}
        self.map_by_id = {flow_map.id: flow_map for flow_map in service.flow_maps}
        operations: dict[str, list[MappingOperation]] = {}
        for operation in service.mapping_operations:
            operations.setdefault(operation.flow_map_id, []).append(operation)
        for items in operations.values():
            items.sort(key=lambda item: item.map_operation_order)
        self.operations = operations
        self.calls = {call.node_id: call for call in logic.calls}
        self.call_by_index = {call.index: call for call in logic.calls}
        self.exits = {item.node_id: item for item in logic.exits}
        self.decisions = {item.node_id: item for item in logic.decisions}
        self.limits: list[str] = []
        self.unfollowed: dict[str, list[str]] = {}
        self.decision_keys: dict[str, tuple[Key, ...]] = {}
        # (decision id, field) where the decision names one list element (`/items[1]/x`).
        self.element_fields: set[tuple[str, Key]] = set()
        self.keys = self._tracked_keys()
        self.key_set = frozenset(self.keys)
        # Every prefix of a followed field -> the followed fields at or under it.
        self.under: dict[Key, list[Key]] = {}
        for key in self.keys:
            for length in range(1, len(key) + 1):
                self.under.setdefault(key[:length], []).append(key)
        self.defs: list[_Def] = []
        self.def_index: dict[tuple[OriginKind, str | None, str | None, Key], int] = {}
        self.snapshots: dict[str, dict[Key, _Value]] = {}
        self.blind: dict[str, str] = {}  # decision id -> "scope" or "too_deep"
        self.too_deep = False
        self.unstable = False
        self.input_fields = list(service.signature.inputs)

    # indexing -------------------------------------------------------------------------------

    def _index(self, node: FlowNode, parent: FlowNode | None) -> None:
        self.nodes[node.id] = node
        self.parent[node.id] = parent
        self.position[node.id] = len(self.position)
        for child in node.children:
            self._index(child, node)

    def _flow_map(self, node: FlowNode) -> FlowMap | None:
        return self.maps.get(node.structural_path)

    def _mode(self, node: FlowNode) -> str:
        flow_map = self._flow_map(node)
        mode = flow_map.mode if flow_map is not None and flow_map.mode else None
        return (mode or node.attributes.get("MODE") or "").strip().upper()

    def _ops(self, node: FlowNode) -> list[MappingOperation]:
        flow_map = self._flow_map(node)
        return self.operations.get(flow_map.id, []) if flow_map is not None else []

    # which fields to follow -----------------------------------------------------------------

    def _decision_fields(self, decision: Decision) -> tuple[Key, ...]:
        reasons: list[str] = []
        found: list[Key] = []
        if decision.mode is DecisionMode.SWITCH:
            if decision.switch is not None:
                found.append(decision.switch.base())
                if decision.switch.segments != decision.switch.base():
                    self.element_fields.add((decision.id, decision.switch.base()))
            else:
                reasons.append("no_switch")
        else:
            for case in decision.cases:
                condition = case.condition
                if condition.kind is ConditionKind.WITHHELD:
                    reasons.append("labels_withheld")
                elif condition.kind is ConditionKind.EXPRESSION and not condition.refs_parsed:
                    reasons.append("expression_not_split")
                for ref in condition.refs:
                    if ref.segments != ref.base():
                        self.element_fields.add((decision.id, ref.base()))
                    if ref.base() not in found:
                        found.append(ref.base())
        if len(found) > MAX_PATHS_PER_DECISION:
            reasons.append("too_many_fields")
            found = found[:MAX_PATHS_PER_DECISION]
        if reasons:
            self.unfollowed[decision.id] = list(dict.fromkeys(reasons))
        return tuple(key for key in found if key)

    def _tracked_keys(self) -> tuple[Key, ...]:
        tracked: dict[Key, None] = {}
        limited = False
        for position, decision in enumerate(self.logic.decisions):
            if position >= MAX_DECISIONS:
                self.unfollowed.setdefault(decision.id, []).append("decision_limit")
                continue
            keys = self._decision_fields(decision)
            self.decision_keys[decision.id] = keys
            for key in keys:
                if key in tracked:
                    continue
                if len(tracked) >= MAX_TRACKED_PATHS:
                    limited = True
                    continue
                tracked[key] = None
        if len(self.logic.decisions) > MAX_DECISIONS:
            self.limits.append(
                f"only the fields of the first {MAX_DECISIONS} decisions are followed"
            )
        # Fields copied into followed fields, a bounded number of steps back.
        copies: dict[str, list[tuple[Key, Key]]] = {}
        for operation in self.service.mapping_operations:
            if operation.operation_type is not MappingOperationType.COPY:
                continue
            flow_map = self.map_by_id.get(operation.flow_map_id)
            mode = (flow_map.mode or "").upper() if flow_map is not None else ""
            if mode in ("INVOKEINPUT", "INVOKEOUTPUT"):
                continue  # transformer maps: one side is not the pipeline (S18)
            target = _endpoint_ref(operation.target_endpoint)
            source = _endpoint_ref(operation.source_endpoint)
            if target is None or source is None or not target.base() or not source.base():
                continue
            copies.setdefault(target.base()[0], []).append((target.base(), source.base()))
        frontier = list(tracked)
        for _round in range(MAX_COPY_CHAIN):
            added: list[Key] = []
            for key in frontier:
                for written, read in copies.get(key[0], ()):
                    if len(written) > len(key) or key[: len(written)] != written:
                        continue
                    candidate = read + key[len(written) :]
                    if candidate in tracked:
                        continue
                    if len(tracked) >= MAX_TRACKED_PATHS:
                        limited = True
                        continue
                    tracked[candidate] = None
                    added.append(candidate)
            frontier = added
        if limited:
            self.limits.append(f"at most {MAX_TRACKED_PATHS} fields are followed per service")
        return tuple(tracked)

    # definitions ----------------------------------------------------------------------------

    def _definition(
        self,
        kind: OriginKind,
        anchor: str | None,
        tag: str | None,
        key: Key,
        *,
        certainty: Certainty,
        weak: bool,
        phase: int = 0,
        order: int = 0,
    ) -> _Def:
        ident = (kind, anchor, tag, key)
        number = self.def_index.get(ident)
        if number is None:
            number = len(self.defs)
            self.def_index[ident] = number
            node = self.nodes.get(anchor or "")
            self.defs.append(
                _Def(
                    number=number,
                    kind=kind,
                    key=key,
                    anchor=anchor,
                    phase=phase,
                    order=order,
                    certainty=certainty,
                    weak=weak,
                    line=node.source.line if node is not None else None,
                    source=node.source if node is not None else None,
                )
            )
            return self.defs[number]
        existing = self.defs[number]
        existing.certainty = weakest((existing.certainty, certainty))
        existing.weak = existing.weak or weak
        return existing

    def _initial(self, key: Key) -> int:
        declared, exact = _declared_match(self.input_fields, key)
        if declared is not None:
            item = self._definition(
                OriginKind.SERVICE_INPUT,
                None,
                None,
                key,
                certainty=Certainty.OBSERVED if exact else Certainty.POSSIBLE,
                weak=False,
            )
            item.declared = declared
        else:
            item = self._definition(
                OriginKind.CALLER, None, None, key, certainty=Certainty.DERIVED, weak=False
            )
        return item.number

    def _may_be_absent(self, numbers: Iterable[int]) -> bool:
        return any(self.defs[number].kind in ABSENT_KINDS for number in numbers)

    def _havoc(self, state: _State, node: FlowNode, reason: str, rules: tuple[str, ...]) -> _State:
        """Every followed field may have been changed by `node` in a way that is not followed."""
        result: _State = {}
        for key, (numbers, calls) in state.items():
            item = self._definition(
                OriginKind.UNKNOWN, node.id, reason, key, certainty=Certainty.UNKNOWN, weak=True
            )
            item.notes.add(reason)
            item.rules.update(rules)
            result[key] = (numbers | {item.number}, calls)
        return result

    # mapping lines --------------------------------------------------------------------------

    def _write(
        self,
        operation: MappingOperation,
        role: MapRole,
        anchor: str,
        call_node: str | None,
        phase: int,
        inputs: tuple[PipelineRef, ...] = (),
    ) -> _Write | None:
        kind = operation.operation_type
        endpoint = (
            operation.delete_endpoint
            if kind is MappingOperationType.DELETE
            else operation.target_endpoint
        )
        target = _endpoint_ref(endpoint)
        if target is None or not target.base():
            return None
        source: Key | None = None
        source_indexed = False
        if kind is MappingOperationType.COPY:
            ref = _endpoint_ref(operation.source_endpoint)
            source = ref.base() if ref is not None and ref.base() else None
            source_indexed = ref is not None and ref.segments != ref.base()
        return _Write(
            op=operation,
            kind=kind,
            target=target.base(),
            indexed=target.segments != target.base(),
            source=source,
            source_indexed=source_indexed,
            role=role,
            anchor=anchor,
            call_node=call_node,
            phase=phase,
            inputs=inputs,
        )

    def _map_writes(
        self, node: FlowNode, role: MapRole, anchor: str, call_node: str | None, phase: int
    ) -> list[_Write]:
        writes = [
            write
            for operation in self._ops(node)
            if (write := self._write(operation, role, anchor, call_node, phase)) is not None
        ]
        for child in node.children:
            if child.type is FlowNodeType.MAPINVOKE:
                writes += self._transformer_writes(child)
        return writes

    def _transformer_writes(self, node: FlowNode) -> list[_Write]:
        inputs: list[PipelineRef] = []
        output_maps: list[FlowNode] = []
        for child in node.children:
            if child.type is not FlowNodeType.MAP:
                continue
            mode = self._mode(child)
            if mode == "INVOKEOUTPUT":
                output_maps.append(child)
            elif mode == "INVOKEINPUT":
                for operation in self._ops(child):
                    if operation.operation_type is MappingOperationType.COPY:
                        ref = _endpoint_ref(operation.source_endpoint)
                        if ref is not None and ref.base() and ref not in inputs:
                            inputs.append(ref)
        shown = tuple(inputs[:MAX_TRANSFORMER_INPUTS])
        return [
            write
            for child in output_maps
            for operation in self._ops(child)
            if (
                write := self._write(
                    operation, MapRole.TRANSFORMER_OUTPUT, node.id, node.id, 0, shown
                )
            )
            is not None
        ]

    def _overlapping(self, path: Key) -> list[Key]:
        """Followed fields that are `path`, lie inside it, or contain it (in that order)."""
        found = list(self.under.get(path, ()))
        found += [path[:length] for length in range(1, len(path)) if path[:length] in self.key_set]
        return found

    def _apply(self, writes: list[_Write], state: _State) -> _State:
        """One MAP (or one map of an INVOKE): every line reads the state before it (S19)."""
        if not writes:
            return state
        affected: dict[Key, list[_Write]] = {}
        for write in writes:
            for key in self._overlapping(write.target):
                affected.setdefault(key, []).append(write)
        if not affected:
            return state
        result = dict(state)
        for key, items in affected.items():
            several = len(items) > 1
            numbers: set[int] = set()
            all_weak = True
            for write in items:
                number, weak = self._line_definition(write, key, state, several)
                numbers.add(number)
                all_weak = all_weak and weak
            defs, calls = state[key]
            result[key] = (defs | numbers, calls) if all_weak else (frozenset(numbers), ())
        return result

    def _line_definition(
        self, write: _Write, key: Key, before: _State, several: bool
    ) -> tuple[int, bool]:
        operation = write.op
        target = write.target
        certainty = Certainty.OBSERVED
        weak = False
        rules: set[str] = set()
        notes: set[str] = set()
        snapshot: _Value | None = None
        source_key: Key | None = None
        followed = True
        value: str | None = None
        template = False
        if len(target) > len(key):
            kind = OriginKind.PARTIAL
            weak = True
            certainty = Certainty.POSSIBLE
        elif write.kind is MappingOperationType.DELETE:
            kind = OriginKind.DROPPED
        elif write.kind is MappingOperationType.SET:
            kind = OriginKind.SET
            value = _literal_text(operation)
            template = _attr_true(operation, "VARIABLES") or _attr_true(
                operation, "GLOBALVARIABLES"
            )
            if template:
                rules.add("S21")
            if len(target) < len(key):
                notes.add("document_value")
            if (operation.technical_attrs.get("OVERWRITE") or "true").strip().lower() == "false":
                weak = True
                certainty = Certainty.POSSIBLE
                rules.add("S21")
                notes.add("overwrite_off")
        elif write.role is MapRole.TRANSFORMER_OUTPUT:
            kind = OriginKind.TRANSFORMER
            source_key = write.source + key[len(target) :] if write.source else None
            # The output may be absent, and a copy from an absent field changes nothing (S20).
            weak = True
            certainty = Certainty.POSSIBLE
            rules.update(("S18", "S20"))
            notes.add("source_may_be_absent")
        else:
            kind = OriginKind.COPY
            if write.source is None:
                followed = False
                weak = True
                certainty = Certainty.POSSIBLE
                notes.add("source_unknown")
            else:
                source_key = write.source + key[len(target) :]
                snapshot = before.get(source_key)
                if snapshot is None:
                    followed = False
                    weak = True
                    certainty = Certainty.POSSIBLE
                    rules.add("S20")
                    notes.add("not_followed")
                elif self._may_be_absent(snapshot[0]) or write.source_indexed:
                    weak = True
                    certainty = Certainty.POSSIBLE
                    rules.add("S20")
                    notes.add("source_may_be_absent")
        if write.indexed:
            weak = True
            certainty = Certainty.POSSIBLE
            notes.add("list_element")
        if operation.unknown_attrs:
            weak = True
            certainty = Certainty.POSSIBLE
            rules.add("S25")
            notes.add("conditional")
        if several:
            certainty = Certainty.POSSIBLE
            rules.add("S19")
            notes.add("several_writes")
        if write.role is MapRole.CALL_INPUT:
            rules.add("S17")
            certainty = weakest((certainty, Certainty.DERIVED))
        item = self._definition(
            kind,
            write.anchor,
            operation.id,
            key,
            certainty=certainty,
            weak=weak,
            phase=write.phase,
            order=operation.order,
        )
        item.rules.update(rules)
        item.notes.update(notes)
        item.call_node = write.call_node
        item.role = write.role
        item.operation = write.kind
        item.written = target if target != key else None
        item.source_key = source_key
        item.followed = item.followed and followed
        item.value = value
        item.template = template
        item.inputs = write.inputs
        item.line = operation.source.line or item.line
        item.source = operation.source
        if snapshot is not None:
            item.sources.update(snapshot[0])
        return item.number, weak

    # calls ----------------------------------------------------------------------------------

    def _call_effects(self, node: FlowNode, state: _State, reads: list[Key]) -> _State:
        call = self.calls.get(node.id)
        if call is None:
            return state
        reset = PIPELINE_RESET.get(call.target)
        result: _State = {}
        if reset is not None:
            # clearPipeline keeps the fields its `preserve` list names; that list may come from
            # the input map or from the pipeline, so earlier values stay possible (S26, S27).
            kind = OriginKind.CLEARED if reset == "clears" else OriginKind.RESTORED
            for key, (numbers, calls) in state.items():
                item = self._definition(
                    kind, node.id, None, key, certainty=Certainty.POSSIBLE, weak=True, phase=1
                )
                item.rules.add("S26" if kind is OriginKind.CLEARED else "S27")
                item.call_node = node.id
                result[key] = (numbers | {item.number}, calls)
            return result
        signature = self.signatures.get(call.target)
        outputs = list(signature.outputs) if signature is not None else []
        for key, (numbers, calls) in state.items():
            declared = _declared_match(outputs, key)[0] if outputs else None
            notes = []
            if declared is not None:
                notes.append("declared_output")
            if any(_overlaps(read, key) for read in reads):
                notes.append("output_map_reads")
            if not notes:
                result[key] = (numbers, _merge_calls(calls, (call.index,)))
                continue
            item = self._definition(
                OriginKind.CALL_RESPONSE,
                node.id,
                None,
                key,
                certainty=Certainty.POSSIBLE,
                weak=True,
                phase=1,
            )
            item.rules.add("S16")
            item.notes.update(notes)
            item.call_node = node.id
            item.declared = item.declared or declared
            result[key] = (numbers | {item.number}, calls)
        return result

    # the walk -------------------------------------------------------------------------------

    def run(self) -> FlowLineage:
        initial: _State = {key: (frozenset({self._initial(key)}), ()) for key in self.keys}
        self._walk(self.root, initial, 0, 0, fails=False)
        if self.too_deep:
            self.limits.append(f"steps nested deeper than {MAX_DEPTH} levels are not followed")
        if self.unstable:
            self.limits.append("some loops did not settle; fields they change are not followed")
        return self._result()

    def _walk(
        self, node: FlowNode, state: _State | None, depth: int, loops: int, *, fails: bool
    ) -> _Result:
        """Walk `node` from `state`.

        `fails` says whether the caller uses the states in which `node` may fail (a CATCH, a
        later alternative, an EXIT-ON DONE sequence or a REPEAT does); without it they are not
        collected, which keeps large services fast.
        """
        if state is None:
            return _Result(None, None, [])
        if depth > MAX_DEPTH:
            self.too_deep = True
            return self._blind(node, state, "too_deep", ())
        if any(item.name.strip().upper() == "SCOPE" for item in node.unknown_attributes):
            return self._blind(node, state, "scope", ("S24",))
        return self._settle(node, self._dispatch(node, state, depth, loops, fails))

    def _blind(self, node: FlowNode, state: _State, reason: str, rules: tuple[str, ...]) -> _Result:
        """`node` is not followed: every field may change, and its decisions get no origins."""
        changed = self._havoc(state, node, reason, rules)
        inside: set[str] = set()
        for inner in subtree(node):
            inside.add(inner.id)
            decision = self.decisions.get(inner.id)
            if decision is not None:
                self.blind.setdefault(decision.id, reason)
        exits: list[tuple[str, _State]] = []
        for inner in subtree(node):
            effect = self.exits.get(inner.id)
            if effect is not None and effect.reach_id not in inside:
                exits.append((inner.id, changed))
        return self._settle(node, _Result(changed, changed, exits))

    def _settle(self, node: FlowNode, result: _Result) -> _Result:
        """Take in the EXITs that end at `node`; pass the others up."""
        if not result.exits:
            return result
        normal, failed = result.normal, result.failed
        remaining: list[tuple[str, _State]] = []
        for exit_id, state in result.exits:
            effect = self.exits.get(exit_id)
            reach = effect.reach_id if effect is not None else None
            if reach is None:
                # The EXIT may end anywhere, including here.
                normal = _join(normal, state)
                failed = _join(failed, state)
                remaining.append((exit_id, state))
            elif reach == node.id:
                if effect is not None and effect.signal == "FAILURE":
                    failed = _join(failed, state)
                else:
                    normal = _join(normal, state)
            else:
                remaining.append((exit_id, state))
        return _Result(normal, failed, remaining)

    def _dispatch(
        self, node: FlowNode, state: _State, depth: int, loops: int, fails: bool
    ) -> _Result:
        kind = node.type
        if kind is FlowNodeType.EXIT:
            return _Result(None, None, [(node.id, state)])
        if kind is FlowNodeType.MAP:
            after = self._apply(self._map_writes(node, MapRole.STEP, node.id, None, 0), state)
            return _Result(after, _join(state, after) if fails else None, [])
        if kind is FlowNodeType.INVOKE:
            return self._invoke(node, state, fails)
        if kind is FlowNodeType.BRANCH:
            return self._branch(node, state, depth, loops, fails)
        if kind is FlowNodeType.LOOP:
            return self._loop(node, state, depth, loops, fails)
        if kind is FlowNodeType.REPEAT:
            return self._repeat(node, state, depth, loops)
        if is_alternatives(node):
            return self._alternatives(node, state, depth, loops)
        if kind in (FlowNodeType.FLOW, FlowNodeType.SEQUENCE, FlowNodeType.BRANCH_CASE):
            return self._sequence(node, state, depth, loops, fails)
        # A transformer outside a MAP changes nothing itself.
        return _Result(state, state if fails else None, [])

    def _invoke(self, node: FlowNode, state: _State, fails: bool) -> _Result:
        maps = [child for child in node.children if child.type is FlowNodeType.MAP]
        outputs = [child for child in maps if self._mode(child) == "OUTPUT"]
        inputs = [child for child in maps if child not in outputs]
        call_node = node.id if node.id in self.calls else None
        before_call = state
        for child in inputs:
            writes = self._map_writes(child, MapRole.CALL_INPUT, node.id, call_node, 0)
            before_call = self._apply(writes, before_call)
        reads = [
            ref.base()
            for child in outputs
            for operation in self._ops(child)
            if operation.operation_type is MappingOperationType.COPY
            and (ref := _endpoint_ref(operation.source_endpoint)) is not None
            and ref.base()
        ]
        after_call = self._call_effects(node, before_call, reads)
        after = after_call
        for child in outputs:
            writes = self._map_writes(child, MapRole.CALL_OUTPUT, node.id, call_node, 2)
            after = self._apply(writes, after)
        # The output map may fail part-way too, for example in a transformer.
        failed = _join_all(state, before_call, after_call, after) if fails else None
        return _Result(after, failed, [])

    def _branch(
        self, node: FlowNode, state: _State, depth: int, loops: int, fails: bool
    ) -> _Result:
        decision = self.decisions.get(node.id)
        dead: set[str] = set()
        normal: _State | None = state  # no case matched: the BRANCH does nothing (S7)
        if decision is not None:
            self._snapshot(decision, state)
            dead = {case.node_id for case in decision.cases if case.unreachable_rule}
            if decision.has_default:
                normal = None
        failed: _State | None = state if fails else None
        exits: list[tuple[str, _State]] = []
        for child in node.children:
            if child.id in dead:
                continue
            # A case is a synthetic step: its child is one level below the BRANCH, as in
            # flow_logic.
            inner = depth if child.type is FlowNodeType.BRANCH_CASE else depth + 1
            result = self._walk(child, state, inner, loops, fails=fails)
            normal = _join(normal, result.normal)
            failed = _join(failed, result.failed)
            exits += result.exits
        return _Result(normal, failed, exits)

    def _sequence(
        self, node: FlowNode, state: _State, depth: int, loops: int, fails: bool
    ) -> _Result:
        """Children in order; CATCH runs after a TRY failed, FINALLY after them (S13, S14)."""
        done = sequence_exit_on(node) == "DONE"
        handlers = any(step_form(child) in ("CATCH", "FINALLY") for child in node.children)
        keep = fails or handlers  # this sequence's own failure states are used
        current: _State | None = state
        failed: _State | None = state if keep else None
        try_failed: _State | None = None
        exits: list[tuple[str, _State]] = []
        for child in node.children:
            form = step_form(child)
            if form == "CATCH":
                entry = try_failed if try_failed is not None else failed
                result = self._walk(child, entry, depth + 1, loops, fails=keep)
                current = _join(current, result.normal)
                try_failed = None
            elif form == "FINALLY":
                entry = _join(current, failed)
                result = self._finally(child, entry, exits, depth, loops, keep)
                current = result.normal
            else:
                child_fails = keep or done or form == "TRY"
                result = self._walk(child, current, depth + 1, loops, fails=child_fails)
                if form == "TRY":
                    try_failed = _join(try_failed, result.failed)
                current = _join(result.normal, result.failed) if done else result.normal
            exits += result.exits
            if keep:
                failed = _join_all(failed, result.failed, current)
        return _Result(current, failed, exits)

    def _finally(
        self,
        node: FlowNode,
        entry: _State | None,
        exits: list[tuple[str, _State]],
        depth: int,
        loops: int,
        fails: bool,
    ) -> _Result:
        """FINALLY also runs before an EXIT leaves (S13): those EXITs carry its changes."""
        for _exit_id, state in exits:
            entry = _join(entry, state)
        result = self._walk(node, entry, depth + 1, loops, fails=fails)
        if result.normal is not None:
            finished = result.normal
            exits[:] = [(exit_id, _merge(state, finished)) for exit_id, state in exits]
        return result

    def _alternatives(self, node: FlowNode, state: _State, depth: int, loops: int) -> _Result:
        """EXIT-ON SUCCESS: each child runs after the one before it failed (S10, S15)."""
        entry: _State | None = state
        normal: _State | None = None
        failed: _State | None = state
        exits: list[tuple[str, _State]] = []
        finals: list[FlowNode] = []
        for child in node.children:
            if step_form(child) == "FINALLY":
                finals.append(child)
                continue
            result = self._walk(child, entry, depth + 1, loops, fails=True)
            normal = _join(normal, result.normal)
            failed = _join(failed, result.failed)
            exits += result.exits
            entry = result.failed
        for child in finals:
            result = self._finally(child, _join(normal, failed), exits, depth, loops, True)
            normal = result.normal
            failed = _join(failed, result.failed)
            exits += result.exits
        return _Result(normal, failed, exits)

    def _loop(
        self, node: FlowNode, state: _State, depth: int, loops: int, fails: bool
    ) -> _Result:
        """Body walked until the state at its start settles; zero iterations possible (S29)."""
        if loops >= MAX_LOOP_NESTING:
            entry = self._havoc(state, node, "deep_loop", ())
            result = self._sequence(node, entry, depth, loops + 1, fails)
            normal = _join(entry, result.normal)
            failed = _join(entry, result.failed) if fails else None
            exits = result.exits
        else:
            normal, failed, exits = self._iterate(node, state, depth, loops, zero=True, fails=fails)
        out_array = path_ref(node.out_array)
        if normal is not None and out_array is not None:
            normal = self._collected(node, normal, out_array.base())
        return _Result(normal, failed, exits)

    def _repeat(self, node: FlowNode, state: _State, depth: int, loops: int) -> _Result:
        """A REPEAT runs its children again after a failure or a success (S23)."""
        if loops >= MAX_LOOP_NESTING:
            entry = self._havoc(state, node, "deep_loop", ())
            result = self._sequence(node, entry, depth, loops + 1, True)
            return _Result(
                _join(result.normal, result.failed), _join(entry, result.failed), result.exits
            )
        normal, failed, exits = self._iterate(node, state, depth, loops, zero=False, fails=True)
        return _Result(_join(normal, failed), failed, exits)

    def _iterate(
        self, node: FlowNode, state: _State, depth: int, loops: int, *, zero: bool, fails: bool
    ) -> tuple[_State | None, _State | None, list[tuple[str, _State]]]:
        entry = state
        normal: _State | None = state if zero else None
        failed: _State | None = state if fails else None
        exits: list[tuple[str, _State]] = []
        for _pass in range(MAX_PASSES):
            result = self._sequence(node, entry, depth, loops + 1, fails)
            normal = _join(normal, result.normal)
            failed = _join(failed, result.failed)
            exits += result.exits
            again = _merge(state, _join(result.normal, None if zero else result.failed))
            if again == entry:
                break
            entry = again
        else:
            # Not settled: every field may still change, on every way out of the loop.
            self.unstable = True
            if normal is not None:
                normal = self._havoc(normal, node, "deep_loop", ())
            if failed is not None:
                failed = self._havoc(failed, node, "deep_loop", ())
            exits = [
                (exit_id, self._havoc(exit_state, node, "deep_loop", ()))
                for exit_id, exit_state in exits
            ]
        return normal, failed, exits

    def _collected(self, node: FlowNode, state: _State, out_array: Key) -> _State:
        if not out_array:
            return state
        result = dict(state)
        for key in self._overlapping(out_array):
            numbers, calls = state[key]
            item = self._definition(
                OriginKind.COLLECTED, node.id, None, key, certainty=Certainty.DERIVED, weak=True
            )
            item.rules.add("S22")
            result[key] = (numbers | {item.number}, calls)
        return result

    def _snapshot(self, decision: Decision, state: _State) -> None:
        stored = self.snapshots.setdefault(decision.id, {})
        for key in self.decision_keys.get(decision.id, ()):
            value = state.get(key)
            if value is not None:
                stored[key] = _join_value(stored.get(key), value)

    # results --------------------------------------------------------------------------------

    def _result(self) -> FlowLineage:
        variables: list[tuple[Decision, Key, _Value | None]] = []
        for decision in self.logic.decisions:
            for key in self.decision_keys.get(decision.id, ()):
                value = self.snapshots.get(decision.id, {}).get(key)
                variables.append((decision, key, value))
        used: set[int] = set()
        stack = [number for _d, _k, value in variables if value for number in value[0]]
        while stack:
            number = stack.pop()
            if number in used:
                continue
            used.add(number)
            stack.extend(self.defs[number].sources)
        ordered = sorted((self.defs[number] for number in used), key=self._sort_key)
        names = {item.number: f"O{index}" for index, item in enumerate(ordered, 1)}
        origins = tuple(self._origin(item, names) for item in ordered)
        built = tuple(
            self._variable(decision, key, value, names) for decision, key, value in variables
        )
        return FlowLineage(
            service=self.service.identity.full_name,
            variables=built,
            origins=origins,
            unfollowed={key: tuple(value) for key, value in self.unfollowed.items()},
            limits=tuple(dict.fromkeys(self.limits)),
        )

    def _sort_key(self, item: _Def) -> tuple[int, int, int, Key, int]:
        # Document order; the service's inputs and the caller's pipeline come last.
        position = self.position[item.anchor] if item.anchor else len(self.position)
        return (position, item.phase, item.order, item.key, _KIND_RANK[item.kind])

    def _ordered(self, numbers: Iterable[int]) -> list[int]:
        return sorted(numbers, key=lambda number: self._sort_key(self.defs[number]))

    def _origin(self, item: _Def, names: dict[int, str]) -> Origin:
        call = self.calls.get(item.call_node or "")
        return Origin(
            id=names[item.number],
            kind=item.kind,
            path=PipelineRef(item.key),
            certainty=item.certainty,
            rules=sort_rules(item.rules),
            weak=item.weak,
            node_id=item.anchor,
            call_id=call.id if call is not None else None,
            map_role=item.role,
            operation=item.operation,
            written_path=PipelineRef(item.written) if item.written else None,
            source_path=PipelineRef(item.source_key) if item.source_key else None,
            source_origins=tuple(
                names[number] for number in self._ordered(item.sources) if number in names
            ),
            source_followed=item.followed,
            value=item.value,
            template=item.template,
            inputs=item.inputs,
            declared_path=PipelineRef(item.declared) if item.declared else None,
            notes=tuple(sorted(item.notes)),
            guard=self.logic.guard_of(item.anchor) if item.anchor else Guard(),
            line=item.line,
            source=item.source,
        )

    def _variable(
        self, decision: Decision, key: Key, value: _Value | None, names: dict[int, str]
    ) -> VariableOrigins:
        notes: list[str] = []
        blind = self.blind.get(decision.id)
        if blind is not None:
            notes.append(blind)
        if key not in self.key_set:
            notes.append("not_followed")
        element = (decision.id, key) in self.element_fields
        if element:
            notes.append("list_element")  # origins are those of the whole field
        numbers = self._ordered(value[0]) if value is not None else []
        calls = [self.call_by_index[index] for index in (value[1] if value is not None else ())]
        first = self.defs[numbers[0]] if len(numbers) == 1 else None
        unique = (
            first is not None
            and not element
            and not calls
            and not first.weak
            and first.certainty is Certainty.OBSERVED
            and first.kind is not OriginKind.CALLER
        )
        return VariableOrigins(
            decision_id=decision.id,
            path=PipelineRef(key),
            reached=value is not None or blind is not None,
            origins=tuple(names[number] for number in numbers),
            unique=unique,
            absent_possible=self._may_be_absent(numbers),
            calls_in_between=tuple(call.id for call in calls[:MAX_CALLS_KEPT]),
            more_calls_in_between=len(calls) > MAX_CALLS_KEPT,
            depends_on_calls=self._depends(numbers),
            loop_path=self._loop_path(decision, key),
            notes=tuple(notes),
        )

    def _depends(self, numbers: Iterable[int]) -> tuple[str, ...]:
        """Calls whose responses may end up in the field, through copies."""
        found: set[str] = set()
        seen: set[int] = set()
        stack = list(numbers)
        while stack:
            number = stack.pop()
            if number in seen:
                continue
            seen.add(number)
            item = self.defs[number]
            if item.kind in (OriginKind.CALL_RESPONSE, OriginKind.TRANSFORMER) and item.call_node:
                found.add(item.call_node)
            if item.kind is OriginKind.COPY:
                stack.extend(item.sources)
        calls = sorted(
            (self.calls[node_id] for node_id in found if node_id in self.calls),
            key=lambda call: call.index,
        )
        return tuple(call.id for call in calls)

    def _loop_path(self, decision: Decision, key: Key) -> PipelineRef | None:
        parent = self.parent.get(decision.node_id)
        while parent is not None:
            if parent.type is FlowNodeType.LOOP:
                array = path_ref(parent.in_array)
                if array is not None and array.base() and _overlaps(array.base(), key):
                    return PipelineRef(array.base())
            parent = self.parent.get(parent.id)
        return None


# --- helpers -------------------------------------------------------------------------------


def _endpoint_ref(endpoint: MappingEndpoint | None) -> PipelineRef | None:
    return path_ref(endpoint.raw_path) if endpoint is not None else None


def _overlaps(first: Key, second: Key) -> bool:
    shorter = min(len(first), len(second))
    return shorter > 0 and first[:shorter] == second[:shorter]


def _attr_true(operation: MappingOperation, name: str) -> bool:
    return (operation.technical_attrs.get(name) or "").strip().lower() == "true"


def _literal_text(operation: MappingOperation) -> str | None:
    literal = operation.literal
    if literal is None or literal.disclosure is not LiteralDisclosure.INCLUDED:
        return None
    return literal.value


def _declared_match(fields: list[SignatureField], key: Key) -> tuple[Key | None, bool]:
    """The declared field `key` names or lies inside, and whether it is that exact field."""
    matched: list[str] = []
    current = fields
    for depth, segment in enumerate(key):
        if depth >= MAX_DECLARED_DEPTH:
            break
        item = next((candidate for candidate in current if candidate.name == segment), None)
        if item is None:
            break
        matched.append(segment)
        if depth == len(key) - 1:
            return tuple(matched), True
        if not item.children:
            record = bool(item.document_reference) or (item.data_type or "").lower() in (
                "record",
                "recref",
            )
            return (tuple(matched), False) if record else (None, False)
        current = item.children
    return None, False


def _merge_calls(first: tuple[int, ...], second: tuple[int, ...]) -> tuple[int, ...]:
    if first is second or not second:
        return first
    if not first:
        return second
    return tuple(sorted(set(first).union(second))[: MAX_CALLS_KEPT + 1])


def _join_value(first: _Value | None, second: _Value) -> _Value:
    if first is None or first is second:
        return second
    defs = first[0] if first[0] is second[0] else first[0] | second[0]
    return defs, _merge_calls(first[1], second[1])


def _join(first: _State | None, second: _State | None) -> _State | None:
    if first is None:
        return second
    if second is None or first is second:
        return first
    return {key: _join_value(value, second[key]) for key, value in first.items()}


def _merge(first: _State, second: _State | None) -> _State:
    """`_join` for a state that is known to exist."""
    if second is None or first is second:
        return first
    return {key: _join_value(value, second[key]) for key, value in first.items()}


def _join_all(*states: _State | None) -> _State | None:
    result: _State | None = None
    for state in states:
        result = _join(result, state)
    return result
