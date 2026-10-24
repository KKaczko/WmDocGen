"""Deterministic usage and data facts per service.

For every service this answers, from analysed facts only:

- **Used by**: its direct callers, and the entry points that reach it -- triggers, REST or
  SOAP descriptors and other artifacts whose node.ndf names a service on the call path,
  legacy REST v1 handlers (`_get`, `_post`, ... at `/rest/<namespace as path>`), declared
  `processes.yml` entrypoints, and callers that nothing in the analysed packages calls.
- **Data and systems touched**: documents in its signature; platform calls that move data
  (publish, JMS, HTTP, SOAP, files, FTP/SFTP, email, storage) with the object and location
  read from the literal or mapped value of the documented input field; JDBC adapter
  services with the operation, tables and connection decoded from their configuration;
  other opaque services, with the connections their node.ndf names; calls that
  leave the analysed packages, named after a declared external system when one matches.
  Effects of local callees are included with the call chain ("via").

Every fact says how it is known. A location the FLOW does not set is "not determined";
nothing is inferred from names.
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass, replace

from wm_doc.adapters import operation_phrase
from wm_doc.builtins import BuiltinEffect, builtin_effect, is_builtin_name
from wm_doc.callgraph import summary_order
from wm_doc.external_systems import EMPTY_CATALOG, ExternalSystemCatalog, system_label
from wm_doc.ir import (
    AdapterDetails,
    AdapterRole,
    AnalysisResult,
    FlowService,
    Importance,
    LiteralDisclosure,
    MappingOperation,
    MappingOperationType,
    ReferenceTargetKind,
    ServiceDocumentUsageRole,
    ServiceType,
    TriggerDetails,
)
from wm_doc.pseudocode import clean_pipeline_path
from wm_doc.triggers import trigger_summary

MAX_VIA_DEPTH = 6
MAX_EFFECTS = 40
MAX_ENTRY_POINTS = 15
MAX_ENTRY_POINTS_IN_TEXT = 6
MAX_ENTRY_DEPTH = 12
MAX_CALLERS_SHOWN = 10
INPUT_MAP_MODES = {"INPUT", "INVOKEINPUT"}
ADAPTER_KNOWN_FROM = "adapter service configuration"
REST_V1_KIND = "REST v1 handler"
# IS REST v1: a folder is a resource at /rest/<folder path>; services with these names
# handle the HTTP methods.
REST_V1_HANDLERS = {
    "_get": "GET",
    "_post": "POST",
    "_put": "PUT",
    "_patch": "PATCH",
    "_delete": "DELETE",
    "_default": "any other method",
}


@dataclass(frozen=True)
class DataEffect:
    object: str
    action: str
    where: str
    known_from: str
    via: tuple[str, ...] = ()
    # Signature documents describe this service only; they are not inherited by callers.
    propagates: bool = True

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.object, self.action, self.where)


@dataclass(frozen=True)
class EntryPoint:
    kind: str
    name: str
    # Services from the entry service down to the described service, both included.
    path: tuple[str, ...]


@dataclass(frozen=True)
class ServiceFacts:
    service: str
    callers: tuple[str, ...]
    entry_points: tuple[EntryPoint, ...]
    effects: tuple[DataEffect, ...]
    hidden_effects: int = 0

    def text(self) -> str:
        """Deterministic plain-text form, used in prompts and for change detection."""
        lines = ["used by:"]
        if self.callers:
            shown = ", ".join(self.callers[:MAX_CALLERS_SHOWN])
            extra = len(self.callers) - min(len(self.callers), MAX_CALLERS_SHOWN)
            lines.append(f"  called by: {shown}" + (f" and {extra} more" if extra else ""))
        else:
            lines.append("  called by: no service in the analysed packages")
        for entry in self.entry_points[:MAX_ENTRY_POINTS_IN_TEXT]:
            chain = " -> ".join(entry.path)
            lines.append(f"  entry point: {entry.kind} {entry.name}: {chain}")
        if len(self.entry_points) > MAX_ENTRY_POINTS_IN_TEXT:
            extra = len(self.entry_points) - MAX_ENTRY_POINTS_IN_TEXT
            lines.append(f"  ... and {extra} more entry point(s)")
        lines.append("data and systems touched (including services it calls):")
        if not self.effects:
            lines.append("  none found")
        for effect in self.effects:
            via = f" via {' -> '.join(effect.via)}" if effect.via else ""
            lines.append(
                f"  {effect.action}: {effect.object} -> {effect.where} "
                f"[{effect.known_from}]{via}"
            )
        if self.hidden_effects:
            lines.append(f"  ... and {self.hidden_effects} more")
        return "\n".join(lines)


def compute_service_facts(
    analysis: AnalysisResult,
    external_systems: ExternalSystemCatalog = EMPTY_CATALOG,
) -> dict[str, ServiceFacts]:
    services = {
        service.identity.full_name: service
        for package in analysis.packages
        for service in package.services
    }
    connections = _connections_by_source(analysis)
    adapter_connections = {
        artifact.full_name: artifact.adapter
        for artifact in analysis.namespace_artifacts
        if artifact.adapter is not None and artifact.adapter.role is AdapterRole.CONNECTION
    }
    own = {
        name: _own_effects(service, services, connections, external_systems, adapter_connections)
        for name, service in services.items()
    }
    effects = _transitive_effects(services, own)
    callers = _callers(services)
    entries = entry_markers(analysis)
    facts: dict[str, ServiceFacts] = {}
    for name in services:
        all_effects = effects[name]
        facts[name] = ServiceFacts(
            service=name,
            callers=tuple(sorted(callers.get(name, ()), key=str.casefold)),
            entry_points=_entry_points(name, callers, entries),
            effects=tuple(all_effects[:MAX_EFFECTS]),
            hidden_effects=max(len(all_effects) - MAX_EFFECTS, 0),
        )
    return facts


def _connections_by_source(analysis: AnalysisResult) -> dict[str, list[str]]:
    connections: dict[str, list[str]] = defaultdict(list)
    for reference in analysis.artifact_references:
        known = connections[reference.source_name]
        if reference.target_kind is ReferenceTargetKind.ARTIFACT and (
            reference.target_name not in known
        ):
            known.append(reference.target_name)
    return connections


def _own_effects(
    service: FlowService,
    services: dict[str, FlowService],
    connections: dict[str, list[str]],
    external_systems: ExternalSystemCatalog,
    adapter_connections: dict[str, AdapterDetails] | None = None,
) -> list[DataEffect]:
    effects: list[DataEffect] = []
    if service.adapter is not None:
        effects.append(adapter_effect(service.adapter, adapter_connections or {}))
    for dependency in sorted(
        service.service_document_dependencies, key=lambda item: item.target_document.casefold()
    ):
        document = f"document `{dependency.target_document}`"
        if dependency.usage_role in (
            ServiceDocumentUsageRole.INPUT,
            ServiceDocumentUsageRole.INPUT_OUTPUT,
        ):
            effects.append(
                DataEffect(document, "receives", "service input", "signature", propagates=False)
            )
        if dependency.usage_role in (
            ServiceDocumentUsageRole.OUTPUT,
            ServiceDocumentUsageRole.INPUT_OUTPUT,
        ):
            effects.append(
                DataEffect(document, "returns", "service output", "signature", propagates=False)
            )
    resolved = {dep.target_service: dep.resolved for dep in service.unique_dependencies}
    for call in service.call_occurrences:
        target = call.target
        effect = builtin_effect(target)
        if effect is not None:
            if effect.data is not None:
                effects.append(_platform_effect(service, call.id, effect))
            continue
        if is_builtin_name(target):
            continue
        if call.target_classification.importance is Importance.LOW:
            continue  # helpers such as *utils* (see the classification config) move no data
        if resolved.get(target, call.resolved):
            callee = services.get(target)
            # An adapter service with a decoded configuration brings its own table effect
            # through the call chain instead.
            if (
                callee is not None
                and callee.service_type is ServiceType.OPAQUE
                and callee.adapter is None
            ):
                effects.append(_opaque_effect(callee, connections))
            continue
        system = external_systems.match(target)
        if system is not None:
            effects.append(
                DataEffect(
                    f"service `{target}`", "calls", system_label(system), "external-systems.yml"
                )
            )
        else:
            effects.append(
                DataEffect(
                    f"service `{target}`",
                    "calls",
                    "outside the analysed packages",
                    "call target only",
                )
            )
    return _dedupe(effects)


def _platform_effect(service: FlowService, call_id: str, effect: BuiltinEffect) -> DataEffect:
    spec = effect.data
    assert spec is not None
    values = _input_values(service, call_id)
    known: set[str] = set()

    def describe(field: str) -> str | None:
        found = values.get(field.casefold())
        if found is None:
            return None
        text, source = found
        known.add(source)
        return text

    object_text = spec.object_label
    for field in spec.object_inputs:
        value = describe(field)
        if value is not None:
            object_text = f"{spec.object_label} {value}"
            break
    where_parts = [
        f"{field} {value}"
        for field in spec.where_inputs
        if (value := describe(field)) is not None
    ]
    if where_parts:
        where = f"{spec.system}: {', '.join(where_parts)}"
    elif spec.where_inputs:
        where = f"{spec.system} (target not determined)"
    else:
        where = spec.system  # the object (e.g. a published document type) is the target
    known_from = " and ".join(sorted(known)) if known else "platform catalog"
    return DataEffect(object_text, effect.label, where, known_from)


def _input_values(service: FlowService, call_id: str) -> dict[str, tuple[str, str]]:
    """Top-level input fields set or mapped into one call: field -> (display, how known)."""
    map_ids = {
        flow_map.id
        for flow_map in service.flow_maps
        if flow_map.parent_call_occurrence_id == call_id
        and (flow_map.mode or "").upper() in INPUT_MAP_MODES
    }
    values: dict[str, tuple[str, str]] = {}
    operations: Iterable[MappingOperation] = sorted(
        (op for op in service.mapping_operations if op.flow_map_id in map_ids),
        key=lambda op: op.map_operation_order,
    )
    for operation in operations:
        target = clean_pipeline_path(
            operation.target_endpoint.raw_path if operation.target_endpoint else None
        )
        if not target:
            continue
        segments = [segment for segment in target.split("/") if segment]
        if len(segments) != 1:
            continue
        field = segments[0].casefold()
        if operation.operation_type is MappingOperationType.SET:
            literal = operation.literal
            if literal is None or not literal.present or literal.is_null_like:
                values[field] = ("(empty)", "literal")
            elif literal.disclosure is LiteralDisclosure.INCLUDED and literal.value is not None:
                values[field] = (f"`{_short(literal.value)}`", "literal")
            else:
                values[field] = ("(value withheld)", "literal")
        elif operation.operation_type is MappingOperationType.COPY:
            source = clean_pipeline_path(
                operation.source_endpoint.raw_path if operation.source_endpoint else None
            )
            if source:
                values.setdefault(field, (f"from `{source}`", "mapped from pipeline"))
    return values


def _short(text: str, limit: int = 120) -> str:
    flat = " ".join(text.split()).replace("`", "'")
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


def adapter_effect(
    details: AdapterDetails, adapter_connections: dict[str, AdapterDetails]
) -> DataEffect:
    """What a JDBC adapter service does, from its decoded configuration."""
    tables = details.tables
    if not tables:
        target = "database"
    elif len(tables) == 1:
        target = f"table `{tables[0]}`"
    else:
        target = "tables " + ", ".join(f"`{table}`" for table in tables)
    return DataEffect(
        target,
        operation_phrase(details),
        connection_label(details.connection, adapter_connections),
        ADAPTER_KNOWN_FROM,
    )


def connection_label(
    connection: str | None, adapter_connections: dict[str, AdapterDetails]
) -> str:
    """The database a connection reaches, with its product and database name when known."""
    if not connection:
        return "database (connection not determined)"
    details = adapter_connections.get(connection)
    extra: list[str] = []
    if details is not None:
        if details.database_product:
            extra.append(details.database_product)
        if details.database_name:
            extra.append(f"database `{details.database_name}`")
    suffix = f" ({', '.join(extra)})" if extra else ""
    return f"database: connection `{connection}`{suffix}"


def _opaque_effect(callee: FlowService, connections: dict[str, list[str]]) -> DataEffect:
    service_type = callee.source_service_type or "opaque"
    found = connections.get(callee.identity.full_name, [])
    if found:
        where = ", ".join(f"`{name}`" for name in found)
        known_from = "reference in its node.ndf"
    else:
        where = "not determined"
        known_from = "service type only"
    return DataEffect(
        f"service `{callee.identity.full_name}`",
        f"calls a `{service_type}` service",
        where,
        known_from,
    )


def _transitive_effects(
    services: dict[str, FlowService], own: dict[str, list[DataEffect]]
) -> dict[str, list[DataEffect]]:
    effects: dict[str, list[DataEffect]] = {}
    for name in summary_order(services.values()):
        collected = list(own[name])
        service = services[name]
        callees = sorted(
            {
                dep.target_service
                for dep in service.unique_dependencies
                if dep.resolved and dep.target_service in services and dep.target_service != name
            },
            key=str.casefold,
        )
        for callee in callees:
            # Inside a call cycle a callee may not be finished yet; use what it does itself.
            for effect in effects.get(callee, own[callee]):
                if not effect.propagates or len(effect.via) >= MAX_VIA_DEPTH:
                    continue
                collected.append(replace(effect, via=(callee, *effect.via)))
        effects[name] = _dedupe(collected)
    return effects


def _dedupe(effects: list[DataEffect]) -> list[DataEffect]:
    seen: set[tuple[str, str, str]] = set()
    result: list[DataEffect] = []
    for effect in effects:
        if effect.key in seen:
            continue
        seen.add(effect.key)
        result.append(effect)
    return result


def _callers(services: dict[str, FlowService]) -> dict[str, set[str]]:
    callers: dict[str, set[str]] = defaultdict(set)
    for name, service in services.items():
        for dependency in service.unique_dependencies:
            target = dependency.target_service
            if dependency.resolved and target in services and target != name:
                callers[target].add(name)
    return callers


def rest_v1_method(full_name: str) -> str | None:
    """The HTTP method a legacy REST handler serves (`_get` -> GET), or None."""
    namespace, _, name = full_name.rpartition(":")
    return REST_V1_HANDLERS.get(name) if namespace else None


def rest_v1_endpoint(full_name: str) -> str | None:
    """`HTTP POST /rest/orders/api` for `orders.api:_post`, or None for other services."""
    method = rest_v1_method(full_name)
    if method is None:
        return None
    path = "/rest/" + full_name.rpartition(":")[0].replace(".", "/")
    if method.startswith("any"):
        return f"{path} (any other HTTP method)"
    return f"HTTP {method} {path}"


def entry_markers(analysis: AnalysisResult) -> dict[str, list[tuple[str, str]]]:
    markers: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for service in analysis.services:
        endpoint = rest_v1_endpoint(service.identity.full_name)
        if endpoint is not None:
            markers[service.identity.full_name].append((REST_V1_KIND, f"`{endpoint}`"))
    triggers = {
        artifact.full_name: artifact.trigger
        for artifact in analysis.namespace_artifacts
        if artifact.trigger is not None
    }
    publishers = notification_publishers(analysis)
    for reference in analysis.artifact_references:
        if reference.target_kind is ReferenceTargetKind.SERVICE:
            trigger = triggers.get(reference.source_name)
            if trigger is not None:
                marker = (trigger.kind, _trigger_marker(reference.source_name, trigger, publishers))
            else:
                marker = (reference.source_kind, f"`{reference.source_name}`")
            if marker not in markers[reference.target_name]:
                markers[reference.target_name].append(marker)
    names = {process.process_id: process.name for process in analysis.processes}
    for entrypoint in analysis.process_entrypoints:
        if entrypoint.resolved_service:
            marker = ("process", f"`{names.get(entrypoint.process_id, entrypoint.process_id)}`")
            if marker not in markers[entrypoint.resolved_service]:
                markers[entrypoint.resolved_service].append(marker)
    return markers


def _trigger_marker(name: str, trigger: TriggerDetails, publishers: dict[str, str]) -> str:
    parts = [trigger_summary(trigger)] if trigger_summary(trigger) else []
    parts += sorted(
        {
            publishers[item.document_type]
            for item in trigger.subscriptions
            if item.document_type in publishers
        },
        key=str.casefold,
    )
    return f"`{name}`" + (f" ({'; '.join(parts)})" if parts else "")


def notification_publishers(analysis: AnalysisResult) -> dict[str, str]:
    """Document type -> the JDBC adapter notification that publishes it."""
    publishers: dict[str, str] = {}
    for artifact in analysis.namespace_artifacts:
        details = artifact.adapter
        if details is None or details.published_document is None:
            continue
        tables = ", ".join(f"table `{table}`" for table in details.tables)
        on = f" on {tables}" if tables else ""
        kind = details.operation or "notification"
        publishers[details.published_document] = (
            f"published by JDBC adapter notification `{artifact.full_name}` ({kind}{on})"
        )
    return publishers


def _entry_points(
    service: str,
    callers: dict[str, set[str]],
    markers: dict[str, list[tuple[str, str]]],
) -> tuple[EntryPoint, ...]:
    """Walk up the callers from *service*, collecting the entry points that reach it."""
    found: list[EntryPoint] = []
    visited = {service}
    queue: deque[tuple[str, ...]] = deque([(service,)])
    while queue and len(found) < MAX_ENTRY_POINTS:
        path = queue.popleft()
        node = path[0]
        for kind, name in markers.get(node, []):
            found.append(EntryPoint(kind, name, path))
        node_callers = sorted(callers.get(node, ()), key=str.casefold)
        if not node_callers and node != service and not markers.get(node):
            found.append(EntryPoint("service with no callers", f"`{node}`", path))
        if len(path) >= MAX_ENTRY_DEPTH:
            continue
        for caller in node_callers:
            if caller not in visited:
                visited.add(caller)
                queue.append((caller, *path))
    return tuple(found[:MAX_ENTRY_POINTS])
