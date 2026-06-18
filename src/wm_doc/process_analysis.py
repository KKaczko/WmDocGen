from __future__ import annotations

import hashlib
from collections import Counter, defaultdict, deque
from dataclasses import dataclass

from wm_doc.ir import (
    AnalysisFinding,
    DocumentDependency,
    FindingSeverity,
    FindingStatus,
    FlowService,
    ProcessDefinition,
    ProcessDependencyEdge,
    ProcessDocumentRelationship,
    ProcessDocumentRelationshipRole,
    ProcessEntrypoint,
    ProcessEntrypointStatus,
    ProcessServiceMembership,
    ProcessUnresolvedCall,
    ServiceDocumentDependency,
    ServiceDocumentUsageRole,
    SourceReference,
    TechnicalEntrypointCandidate,
    UniqueDependency,
)


@dataclass(frozen=True)
class ProcessAnalysisOutput:
    processes: list[ProcessDefinition]
    process_entrypoints: list[ProcessEntrypoint]
    process_service_memberships: list[ProcessServiceMembership]
    process_dependency_edges: list[ProcessDependencyEdge]
    process_unresolved_calls: list[ProcessUnresolvedCall]
    process_document_relationships: list[ProcessDocumentRelationship]
    technical_entrypoint_candidates: list[TechnicalEntrypointCandidate]
    findings: list[AnalysisFinding]


@dataclass
class _MembershipState:
    minimum_depth: int
    representative_path: tuple[str, ...]
    reached_from: set[str]


def build_process_analysis(
    *,
    processes: list[ProcessDefinition],
    process_entrypoints: list[ProcessEntrypoint],
    services: list[FlowService],
    unique_dependencies: list[UniqueDependency],
    service_document_dependencies: list[ServiceDocumentDependency],
    document_dependencies: list[DocumentDependency],
) -> ProcessAnalysisOutput:
    services_by_name: dict[str, list[FlowService]] = defaultdict(list)
    for service in services:
        services_by_name[service.identity.full_name].append(service)
    unique_service_by_name = {
        name: service_list[0]
        for name, service_list in services_by_name.items()
        if len(service_list) == 1
    }

    resolved_dependencies = [
        dependency for dependency in unique_dependencies if dependency.resolved
    ]
    unresolved_dependencies = [
        dependency for dependency in unique_dependencies if not dependency.resolved
    ]
    adjacency: dict[str, list[UniqueDependency]] = defaultdict(list)
    for dependency in resolved_dependencies:
        adjacency[dependency.source_service].append(dependency)
    for source in list(adjacency):
        adjacency[source] = sorted(adjacency[source], key=_dependency_traversal_key)

    entrypoints_by_process: dict[str, list[ProcessEntrypoint]] = defaultdict(list)
    findings_by_process: dict[str, list[AnalysisFinding]] = defaultdict(list)
    updated_entrypoints: list[ProcessEntrypoint] = []
    for entrypoint in process_entrypoints:
        if entrypoint.status == ProcessEntrypointStatus.DUPLICATE:
            finding = _finding(
                "PROCESS_ENTRYPOINT_DUPLICATE",
                f"Duplicate process entrypoint {entrypoint.declared_target!r} was not traversed.",
                entrypoint.source,
                FindingStatus.PARTIALLY_SUPPORTED,
                FindingSeverity.WARNING,
            )
            findings_by_process[entrypoint.process_id].append(finding)
            updated_entrypoints.append(entrypoint)
            entrypoints_by_process[entrypoint.process_id].append(entrypoint)
            continue
        targets = services_by_name.get(entrypoint.declared_target, [])
        if not targets:
            updated = entrypoint.model_copy(
                update={"status": ProcessEntrypointStatus.NOT_FOUND, "resolved_service": None}
            )
            findings_by_process[entrypoint.process_id].append(
                _finding(
                    "PROCESS_ENTRYPOINT_NOT_FOUND",
                    f"Process entrypoint {entrypoint.declared_target!r} was not found.",
                    entrypoint.source,
                    FindingStatus.UNRESOLVED,
                    FindingSeverity.WARNING,
                )
            )
        elif len(targets) > 1:
            updated = entrypoint.model_copy(
                update={"status": ProcessEntrypointStatus.AMBIGUOUS, "resolved_service": None}
            )
            findings_by_process[entrypoint.process_id].append(
                _finding(
                    "PROCESS_ENTRYPOINT_AMBIGUOUS",
                    f"Process entrypoint {entrypoint.declared_target!r} matched multiple services.",
                    entrypoint.source,
                    FindingStatus.MALFORMED,
                    FindingSeverity.ERROR,
                )
            )
        else:
            updated = entrypoint.model_copy(
                update={
                    "status": ProcessEntrypointStatus.RESOLVED,
                    "resolved_service": targets[0].identity.full_name,
                }
            )
        updated_entrypoints.append(updated)
        entrypoints_by_process[updated.process_id].append(updated)

    memberships: list[ProcessServiceMembership] = []
    process_edges: list[ProcessDependencyEdge] = []
    process_unresolved_calls: list[ProcessUnresolvedCall] = []
    process_document_relationships: list[ProcessDocumentRelationship] = []
    process_entrypoint_service_names: dict[str, set[str]] = {}

    updated_processes: list[ProcessDefinition] = []
    for process in sorted(processes, key=lambda item: item.process_id.casefold()):
        entrypoints = sorted(
            entrypoints_by_process.get(process.process_id, []),
            key=lambda item: (item.declared_target.casefold(), item.id),
        )
        resolved_entrypoints = [
            entrypoint
            for entrypoint in entrypoints
            if entrypoint.status == ProcessEntrypointStatus.RESOLVED
            and entrypoint.resolved_service is not None
        ]
        membership_state = _traverse_process(
            process.process_id, resolved_entrypoints, adjacency
        )
        if not membership_state:
            findings_by_process[process.process_id].append(
                _finding(
                    "PROCESS_SUBGRAPH_EMPTY",
                    "Process has no resolved traversable entrypoints.",
                    process.source,
                    FindingStatus.UNRESOLVED,
                    FindingSeverity.WARNING,
                )
            )
        entrypoint_services = {
            entrypoint.resolved_service
            for entrypoint in resolved_entrypoints
            if entrypoint.resolved_service is not None
        }
        process_entrypoint_service_names[process.process_id] = entrypoint_services
        membership_ids: dict[str, str] = {}
        for service_name, state in sorted(
            membership_state.items(), key=lambda item: item[0].casefold()
        ):
            service = unique_service_by_name[service_name]
            membership_id = _stable_id("process_member", process.process_id, service_name)
            membership_ids[service_name] = membership_id
            memberships.append(
                ProcessServiceMembership(
                    id=membership_id,
                    process_id=process.process_id,
                    service=service_name,
                    service_type=service.service_type,
                    service_analysis_status=service.analysis_status,
                    entrypoint=service_name in entrypoint_services,
                    minimum_depth=state.minimum_depth,
                    directly_called_from_entrypoint=state.minimum_depth == 1,
                    reached_from_entrypoint_ids=sorted(state.reached_from),
                    representative_path_dependency_ids=list(state.representative_path),
                )
            )

        member_names = set(membership_state)
        for dependency in sorted(resolved_dependencies, key=_process_edge_key):
            if dependency.source_service not in member_names:
                continue
            if dependency.target_service not in member_names:
                continue
            edge_id = _stable_id("process_edge", process.process_id, dependency.id)
            process_edges.append(
                ProcessDependencyEdge(
                    id=edge_id,
                    process_id=process.process_id,
                    dependency_id=dependency.id,
                    source_service=dependency.source_service,
                    target_service=dependency.target_service,
                    source_membership_id=membership_ids[dependency.source_service],
                    target_membership_id=membership_ids[dependency.target_service],
                    dependency_kind=dependency.dependency_kind,
                    occurrence_count=dependency.occurrence_count,
                )
            )

        for dependency in sorted(unresolved_dependencies, key=_process_edge_key):
            if dependency.source_service not in member_names:
                continue
            process_unresolved_calls.append(
                ProcessUnresolvedCall(
                    id=_stable_id("process_unresolved", process.process_id, dependency.id),
                    process_id=process.process_id,
                    source_service=dependency.source_service,
                    target_service=dependency.target_service,
                    dependency_kind=dependency.dependency_kind,
                    occurrence_count=dependency.occurrence_count,
                    occurrence_ids=dependency.occurrence_ids,
                    source_samples=dependency.source_samples,
                )
            )

        process_document_relationships.extend(
            _process_document_relationships(
                process.process_id,
                member_names,
                entrypoint_services,
                service_document_dependencies,
                document_dependencies,
            )
        )

        process_findings = [
            *process.findings,
            *sorted(findings_by_process.get(process.process_id, []), key=_finding_key),
        ]
        updated_processes.append(
            process.model_copy(
                update={
                    "entrypoint_ids": [entrypoint.id for entrypoint in entrypoints],
                    "findings": process_findings,
                }
            )
        )

    candidates = _technical_entrypoint_candidates(services, resolved_dependencies)
    process_findings = [
        finding
        for finding_list in findings_by_process.values()
        for finding in finding_list
    ]
    return ProcessAnalysisOutput(
        processes=updated_processes,
        process_entrypoints=sorted(updated_entrypoints, key=_entrypoint_key),
        process_service_memberships=sorted(memberships, key=_membership_key),
        process_dependency_edges=sorted(process_edges, key=_process_dependency_edge_key),
        process_unresolved_calls=sorted(process_unresolved_calls, key=_process_unresolved_key),
        process_document_relationships=sorted(
            process_document_relationships, key=_process_document_relationship_key
        ),
        technical_entrypoint_candidates=candidates,
        findings=sorted(process_findings, key=_finding_key),
    )


def _traverse_process(
    process_id: str,
    resolved_entrypoints: list[ProcessEntrypoint],
    adjacency: dict[str, list[UniqueDependency]],
) -> dict[str, _MembershipState]:
    del process_id
    state: dict[str, _MembershipState] = {}
    visited: set[tuple[str, str]] = set()
    queue = deque[tuple[str, str, int, tuple[str, ...]]]()
    for entrypoint in sorted(
        resolved_entrypoints,
        key=lambda item: ((item.resolved_service or "").casefold(), item.id),
    ):
        if entrypoint.resolved_service is None:
            continue
        queue.append((entrypoint.resolved_service, entrypoint.id, 0, ()))

    while queue:
        service_name, entrypoint_id, depth, path = queue.popleft()
        visit_key = (service_name, entrypoint_id)
        if visit_key in visited:
            continue
        visited.add(visit_key)
        existing = state.get(service_name)
        if existing is None:
            state[service_name] = _MembershipState(
                minimum_depth=depth,
                representative_path=path,
                reached_from={entrypoint_id},
            )
        else:
            existing.reached_from.add(entrypoint_id)
            if depth < existing.minimum_depth or (
                depth == existing.minimum_depth and path < existing.representative_path
            ):
                existing.minimum_depth = depth
                existing.representative_path = path
        for dependency in adjacency.get(service_name, []):
            queue.append(
                (
                    dependency.target_service,
                    entrypoint_id,
                    depth + 1,
                    (*path, dependency.id),
                )
            )
    return state


def _process_document_relationships(
    process_id: str,
    member_names: set[str],
    entrypoint_services: set[str],
    service_document_dependencies: list[ServiceDocumentDependency],
    document_dependencies: list[DocumentDependency],
) -> list[ProcessDocumentRelationship]:
    relationships: list[ProcessDocumentRelationship] = []
    used_documents: set[str] = set()
    for service_dependency in sorted(
        service_document_dependencies, key=_service_document_dependency_key
    ):
        if service_dependency.service not in member_names:
            continue
        used_documents.add(service_dependency.target_document)
        for role in _document_roles(
            service_dependency, service_dependency.service in entrypoint_services
        ):
            relationships.append(
                ProcessDocumentRelationship(
                    id=_stable_id("process_doc", process_id, role.value, service_dependency.id),
                    process_id=process_id,
                    role=role,
                    target_document=service_dependency.target_document,
                    resolved=service_dependency.resolved,
                    occurrence_count=service_dependency.occurrence_count,
                    service=service_dependency.service,
                    dependency_id=service_dependency.id,
                    relationship_kind=service_dependency.dependency_kind,
                )
            )
    for document_dependency in sorted(document_dependencies, key=_document_dependency_key):
        if document_dependency.source_document not in used_documents:
            continue
        relationships.append(
            ProcessDocumentRelationship(
                id=_stable_id(
                    "process_doc", process_id, "document", document_dependency.id
                ),
                process_id=process_id,
                role=ProcessDocumentRelationshipRole.DOCUMENT_DEPENDENCY,
                target_document=document_dependency.target_document,
                resolved=document_dependency.resolved,
                occurrence_count=document_dependency.occurrence_count,
                source_document=document_dependency.source_document,
                dependency_id=document_dependency.id,
                relationship_kind=document_dependency.dependency_kind,
            )
        )
    return relationships


def _document_roles(
    dependency: ServiceDocumentDependency, entrypoint: bool
) -> list[ProcessDocumentRelationshipRole]:
    if dependency.usage_role == ServiceDocumentUsageRole.INPUT_OUTPUT:
        if entrypoint:
            return [
                ProcessDocumentRelationshipRole.ENTRYPOINT_INPUT,
                ProcessDocumentRelationshipRole.ENTRYPOINT_OUTPUT,
            ]
        return [ProcessDocumentRelationshipRole.SERVICE_INPUT_OUTPUT]
    if dependency.usage_role == ServiceDocumentUsageRole.INPUT:
        return [
            ProcessDocumentRelationshipRole.ENTRYPOINT_INPUT
            if entrypoint
            else ProcessDocumentRelationshipRole.SERVICE_INPUT
        ]
    return [
        ProcessDocumentRelationshipRole.ENTRYPOINT_OUTPUT
        if entrypoint
        else ProcessDocumentRelationshipRole.SERVICE_OUTPUT
    ]


def _technical_entrypoint_candidates(
    services: list[FlowService], resolved_dependencies: list[UniqueDependency]
) -> list[TechnicalEntrypointCandidate]:
    incoming = Counter(dependency.target_service for dependency in resolved_dependencies)
    outgoing = Counter(dependency.source_service for dependency in resolved_dependencies)
    candidates: list[TechnicalEntrypointCandidate] = []
    for service in sorted(services, key=lambda item: item.identity.full_name.casefold()):
        if incoming[service.identity.full_name] != 0:
            continue
        candidates.append(
            TechnicalEntrypointCandidate(
                id=_stable_id("entrypoint_candidate", service.identity.full_name),
                service=service.identity.full_name,
                service_type=service.service_type,
                service_analysis_status=service.analysis_status,
                incoming_resolved_dependency_count=0,
                outgoing_dependency_count=outgoing[service.identity.full_name],
                importance=service.classification.importance,
                layer=service.classification.layer,
                reason=(
                    "No incoming resolved local service dependency targets this service "
                    "within the analyzed service set."
                ),
                source=service.source,
            )
        )
    return candidates


def _dependency_traversal_key(dependency: UniqueDependency) -> tuple[str, str, str]:
    return (
        dependency.target_service.casefold(),
        dependency.dependency_kind.value,
        dependency.id,
    )


def _process_edge_key(dependency: UniqueDependency) -> tuple[str, str, str, str]:
    return (
        dependency.source_service.casefold(),
        dependency.target_service.casefold(),
        dependency.dependency_kind.value,
        dependency.id,
    )


def _entrypoint_key(entrypoint: ProcessEntrypoint) -> tuple[str, str, str]:
    return (
        entrypoint.process_id.casefold(),
        entrypoint.declared_target.casefold(),
        entrypoint.id,
    )


def _membership_key(membership: ProcessServiceMembership) -> tuple[str, int, str, str]:
    return (
        membership.process_id.casefold(),
        membership.minimum_depth,
        membership.service.casefold(),
        membership.id,
    )


def _process_dependency_edge_key(edge: ProcessDependencyEdge) -> tuple[str, str, str, str]:
    return (
        edge.process_id.casefold(),
        edge.source_service.casefold(),
        edge.target_service.casefold(),
        edge.id,
    )


def _process_unresolved_key(call: ProcessUnresolvedCall) -> tuple[str, str, str, str]:
    return (
        call.process_id.casefold(),
        call.source_service.casefold(),
        call.target_service.casefold(),
        call.id,
    )


def _process_document_relationship_key(
    relationship: ProcessDocumentRelationship,
) -> tuple[str, str, str, str, str]:
    return (
        relationship.process_id.casefold(),
        relationship.role.value,
        relationship.target_document.casefold(),
        relationship.dependency_id or "",
        relationship.id,
    )


def _service_document_dependency_key(
    dependency: ServiceDocumentDependency,
) -> tuple[str, str, str, str]:
    return (
        dependency.service.casefold(),
        dependency.target_document.casefold(),
        dependency.usage_role.value,
        dependency.id,
    )


def _document_dependency_key(dependency: DocumentDependency) -> tuple[str, str, str]:
    return (
        dependency.source_document.casefold(),
        dependency.target_document.casefold(),
        dependency.id,
    )


def _finding_key(finding: AnalysisFinding) -> tuple[str, str, str]:
    return (finding.source.path.casefold(), finding.code, finding.message)


def _finding(
    code: str,
    message: str,
    source: SourceReference,
    status: FindingStatus,
    severity: FindingSeverity,
) -> AnalysisFinding:
    return AnalysisFinding(
        status=status,
        code=code,
        message=message,
        source=source,
        severity=severity,
    )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
