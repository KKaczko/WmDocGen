"""What a called service may write to the pipeline: a conservative, bottom-up summary.

Stage 7 of the conditional-flow work. A called service shares the caller's pipeline (S16), so
any call may change any field. For a fully analysed FLOW service, the fields it may write or
drop are collected from its own mapping lines (pipeline maps and the output maps of its INVOKE
steps and transformers), LOOP OUT-ARRAYs, `$iteration` (LOOP, REPEAT) and `lastError` (CATCH,
FINALLY), and the summaries of the services it invokes, callees first
(`callgraph.summary_order`). A transformer
is not a callee here: it runs isolated and only its linked outputs reach the pipeline (S18),
which its output map already lists. Anything that is not known makes the summary "unknown"
(may write anything): a platform service (its outputs are not catalogued), a service outside
the analysed packages, a dynamic or unsupported call, a call cycle, a Java service (its
reader does not record every API that changes the pipeline), a service not fully analysed,
an adapter or other opaque service, a name two packages define.

Derived on demand like `effects`, never stored in `analysis.json`. Lineage (`flow_lineage`)
uses it only to drop a call from "calls in between" when its summary proves it cannot touch
the field; it never adds an origin.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from wm_doc.call_targets import classify_finding
from wm_doc.callgraph import summary_order
from wm_doc.flow_paths import path_ref
from wm_doc.ir import (
    CallType,
    FlowNode,
    FlowNodeType,
    FlowService,
    MappingOperationType,
    ServiceAnalysisStatus,
    ServiceType,
)

Key = tuple[str, ...]
MAX_WRITTEN_FIELDS = 500  # more than this and the summary is "unknown"
_TRANSFORMER_INPUT = "INVOKEINPUT"  # a transformer's input map writes its own inputs (S18)


@dataclass(frozen=True, slots=True)
class PipelineWrites:
    """The pipeline fields a service may write or drop; `unknown`: it may change any field."""

    fields: frozenset[Key]
    unknown: bool

    def may_change(self, key: Key) -> bool:
        """Whether a call to the service may change `key` or a field inside or above it."""
        if self.unknown:
            return True
        return any(_overlaps(field, key) for field in self.fields)


UNKNOWN = PipelineWrites(frozenset(), True)


def compute_pipeline_writes(services: Iterable[FlowService]) -> dict[str, PipelineWrites]:
    """The write summary of every analysed service, by full name."""
    services = list(services)
    counts = Counter(service.identity.full_name for service in services)
    by_name = {service.identity.full_name: service for service in services}
    result: dict[str, PipelineWrites] = {}
    for name in summary_order(by_name.values()):
        if counts[name] > 1:
            result[name] = UNKNOWN  # which one Integration Server loads is not known
            continue
        result[name] = _summary(by_name[name], result)
    return result


def _summary(service: FlowService, known: dict[str, PipelineWrites]) -> PipelineWrites:
    if service.analysis_status is not ServiceAnalysisStatus.FULL:
        return UNKNOWN
    if service.service_type is not ServiceType.FLOW:
        # Java included: the source reader records IDataUtil get/put/remove only, not every
        # API that changes the pipeline (cursor inserts, merges, helpers given `pipeline`).
        return UNKNOWN
    fields, unknown = _flow_writes(service)
    for target in _callees(service):
        callee = known.get(target)
        if callee is None or callee.unknown:  # outside, platform, or not done yet (a cycle)
            return UNKNOWN
        fields |= callee.fields
    if unknown or len(fields) > MAX_WRITTEN_FIELDS:
        return UNKNOWN
    return PipelineWrites(frozenset(fields), False)


def _callees(service: FlowService) -> list[str]:
    """Services this one invokes on its own pipeline (transformers excluded, see above)."""
    targets = [
        call.target for call in service.call_occurrences if call.call_type is not CallType.MAPINVOKE
    ]
    return sorted(set(targets))


def _flow_writes(service: FlowService) -> tuple[set[Key], bool]:
    unknown = any(classify_finding(finding) is not None for finding in service.findings)
    modes = {flow_map.id: (flow_map.mode or "").strip().upper() for flow_map in service.flow_maps}
    fields: set[Key] = set()
    for operation in service.mapping_operations:
        if modes.get(operation.flow_map_id) == _TRANSFORMER_INPUT:
            continue
        endpoint = (
            operation.delete_endpoint
            if operation.operation_type is MappingOperationType.DELETE
            else operation.target_endpoint
        )
        ref = path_ref(endpoint.raw_path) if endpoint is not None else None
        if ref is None or not ref.base():
            unknown = True  # a line whose target is not read
            continue
        fields.add(ref.base())
    if service.flow_tree is not None:
        for node in _nodes(service.flow_tree):
            if node.type in (FlowNodeType.LOOP, FlowNodeType.REPEAT):
                fields.add(("$iteration",))  # set by Integration Server itself
            if node.type is FlowNodeType.SEQUENCE and (node.form or "").strip().upper() in (
                "CATCH",
                "FINALLY",
            ):
                fields.add(("lastError",))  # conservatively: the failure may be put there
            if node.type is FlowNodeType.LOOP and node.out_array:
                ref = path_ref(node.out_array)
                if ref is None or not ref.base():
                    unknown = True
                else:
                    fields.add(ref.base())
    return fields, unknown


def _nodes(node: FlowNode) -> Iterable[FlowNode]:
    yield node
    for child in node.children:
        yield from _nodes(child)


def _overlaps(first: Key, second: Key) -> bool:
    shorter = min(len(first), len(second))
    return shorter > 0 and first[:shorter] == second[:shorter]
