from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from wm_doc.ir import (
    AnalysisFinding,
    AnalysisResult,
    DependencyKind,
    DocumentDependency,
    DocumentType,
    FindingSeverity,
    FindingStatus,
    FlowService,
    JavaInvocationTargetStatus,
    ProcessEntrypointStatus,
    ServiceAnalysisStatus,
    ServiceDocumentDependency,
    ServiceType,
    SourceReference,
    UniqueDependency,
)

NAMESPACE_SEGMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
PROCESS_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
MAX_REACHING_ROOT_SAMPLES = 5
MAX_REPRESENTATIVE_PATH_SAMPLES = 3
MAX_SOURCE_SAMPLES = 3


class ScopeSelectorType(StrEnum):
    SERVICE = "SERVICE"
    NAMESPACE = "NAMESPACE"
    PACKAGE = "PACKAGE"
    PROCESS = "PROCESS"


class ScopeInclusionReason(StrEnum):
    ROOT_SERVICE = "ROOT_SERVICE"
    ROOT_NAMESPACE_MEMBER = "ROOT_NAMESPACE_MEMBER"
    ROOT_PACKAGE_MEMBER = "ROOT_PACKAGE_MEMBER"
    ROOT_PROCESS_ENTRYPOINT = "ROOT_PROCESS_ENTRYPOINT"
    DIRECT_DEPENDENCY = "DIRECT_DEPENDENCY"
    TRANSITIVE_DEPENDENCY = "TRANSITIVE_DEPENDENCY"


class ScopeBoundaryStatus(StrEnum):
    DEPTH_LIMIT = "DEPTH_LIMIT"
    EXTERNAL_BUILTIN = "EXTERNAL_BUILTIN"
    OUTSIDE_SNAPSHOT = "OUTSIDE_SNAPSHOT"
    UNRESOLVED = "UNRESOLVED"
    DYNAMIC = "DYNAMIC"
    UNSUPPORTED = "UNSUPPORTED"


class ScopeDocumentInclusionReason(StrEnum):
    DIRECT_SERVICE_DOCUMENT = "DIRECT_SERVICE_DOCUMENT"
    DIRECT_PROCESS_DOCUMENT = "DIRECT_PROCESS_DOCUMENT"
    TRANSITIVE_DOCUMENT = "TRANSITIVE_DOCUMENT"


@dataclass(frozen=True)
class ScopeRequest:
    selector_type: ScopeSelectorType
    selector_value: str
    dependency_depth: int | None = None

    @property
    def depth_label(self) -> str:
        return "all" if self.dependency_depth is None else str(self.dependency_depth)


@dataclass(frozen=True)
class ScopeBuildOutput:
    scope: ScopeResult | None
    exit_code: int = 0
    code: str | None = None
    message: str | None = None

    @property
    def should_publish(self) -> bool:
        return self.scope is not None


@dataclass
class _MembershipState:
    minimum_depth: int
    paths_by_root: dict[str, tuple[str, ...]]
    reasons: set[ScopeInclusionReason]


class ScopeSelector(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    selector_type: ScopeSelectorType
    value: str
    dependency_depth: str


class ScopeRepresentativePathSample(BaseModel):
    model_config = ConfigDict(frozen=True)

    root_service: str
    dependency_ids: list[str] = Field(default_factory=list)


class ScopeServiceMembership(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    selector_id: str
    service: str
    service_id: str
    service_type: ServiceType
    analysis_status: ServiceAnalysisStatus
    is_root: bool
    minimum_depth: int
    inclusion_reasons: list[ScopeInclusionReason] = Field(default_factory=list)
    reaching_root_count: int
    reaching_root_samples: list[str] = Field(default_factory=list)
    reaching_root_samples_omitted: int = 0
    representative_path_samples: list[ScopeRepresentativePathSample] = Field(
        default_factory=list
    )
    representative_path_samples_omitted: int = 0


class ScopeDependencyEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    dependency_id: str
    source_service: str
    target_service: str
    dependency_kind: DependencyKind
    occurrence_count: int


class ScopeBoundary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source_service: str
    target: str
    target_category: str
    dependency_or_call_kind: str
    status: ScopeBoundaryStatus
    occurrence_count: int = 1
    evidence_ids: list[str] = Field(default_factory=list)
    source_samples: list[SourceReference] = Field(default_factory=list)


class ScopeDocumentMembership(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    document: str
    inclusion_reasons: list[ScopeDocumentInclusionReason] = Field(default_factory=list)
    direct: bool
    minimum_document_depth: int
    source_services: list[str] = Field(default_factory=list)
    source_processes: list[str] = Field(default_factory=list)


class ScopeDocumentDependencyEdge(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    dependency_id: str
    source_document: str
    target_document: str
    occurrence_count: int


class ScopeDocumentBoundary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    source: str
    target_document: str
    status: ScopeBoundaryStatus
    occurrence_count: int
    evidence_ids: list[str] = Field(default_factory=list)
    source_samples: list[SourceReference] = Field(default_factory=list)


class ScopeProcessProjection(BaseModel):
    model_config = ConfigDict(frozen=True)

    process_id: str
    process_name: str
    full_member_count: int
    published_member_count: int
    full_edge_count: int
    published_edge_count: int
    boundary_dependency_count: int
    full_unresolved_call_count: int
    published_unresolved_call_count: int
    full_document_relationship_count: int
    published_document_count: int
    entrypoint_count: int
    resolved_entrypoint_count: int


class ScopeMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    selector_type: ScopeSelectorType
    selector_value: str
    dependency_depth: str
    roots_resolved: int = 0
    services_included: int = 0
    root_services_included: int = 0
    services_by_minimum_depth: dict[str, int] = Field(default_factory=dict)
    included_resolved_dependencies: int = 0
    boundary_dependencies: int = 0
    boundary_counts_by_status: dict[str, int] = Field(default_factory=dict)
    documents_included: int = 0
    direct_documents_included: int = 0
    transitive_documents_included: int = 0
    document_boundaries: int = 0
    processes_published: int = 0
    maximum_reached_depth: int = 0
    reaching_root_samples_omitted: int = 0
    representative_path_samples_omitted: int = 0


class ScopeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: str = "scope.v1"
    publication_mode: str = "focused_publication_scope"
    selector: ScopeSelector
    metrics: ScopeMetrics
    root_services: list[str] = Field(default_factory=list)
    service_memberships: list[ScopeServiceMembership] = Field(default_factory=list)
    dependencies: list[ScopeDependencyEdge] = Field(default_factory=list)
    boundaries: list[ScopeBoundary] = Field(default_factory=list)
    document_memberships: list[ScopeDocumentMembership] = Field(default_factory=list)
    document_dependencies: list[ScopeDocumentDependencyEdge] = Field(default_factory=list)
    document_boundaries: list[ScopeDocumentBoundary] = Field(default_factory=list)
    process_projections: list[ScopeProcessProjection] = Field(default_factory=list)
    selected_process_id: str | None = None
    findings: list[AnalysisFinding] = Field(default_factory=list)


def validate_scope_request(request: ScopeRequest) -> AnalysisFinding | None:
    value = request.selector_value.strip()
    if request.selector_type == ScopeSelectorType.SERVICE:
        valid = _valid_service_full_name(value)
    elif request.selector_type == ScopeSelectorType.NAMESPACE:
        valid = _valid_namespace(value)
    elif request.selector_type == ScopeSelectorType.PACKAGE:
        valid = _valid_package_name(value)
    else:
        valid = _valid_process_id(value)
    if valid:
        return None
    return _scope_finding(
        "SCOPE_TARGET_MALFORMED",
        "Scope selector value is malformed for the selected target type.",
        FindingStatus.MALFORMED,
        FindingSeverity.ERROR,
    )


def build_focused_scope(
    analysis: AnalysisResult,
    request: ScopeRequest,
    *,
    process_catalog_available: bool,
) -> ScopeBuildOutput:
    request = ScopeRequest(
        selector_type=request.selector_type,
        selector_value=request.selector_value.strip(),
        dependency_depth=request.dependency_depth,
    )
    malformed = validate_scope_request(request)
    if malformed is not None:
        return ScopeBuildOutput(
            None,
            exit_code=1,
            code=malformed.code,
            message=malformed.message,
        )

    selector = ScopeSelector(
        id=_stable_id(
            "scope_selector",
            request.selector_type.value,
            request.selector_value,
            request.depth_label,
        ),
        selector_type=request.selector_type,
        value=request.selector_value,
        dependency_depth=request.depth_label,
    )
    services = _all_services(analysis)
    services_by_name = _multimap(
        services, key=lambda service: service.identity.full_name
    )
    root_output = _resolve_roots(
        analysis,
        services,
        services_by_name,
        request,
        process_catalog_available=process_catalog_available,
    )
    if root_output.error is not None:
        return ScopeBuildOutput(
            None,
            exit_code=1,
            code=root_output.error.code,
            message=root_output.error.message,
        )
    roots = root_output.roots
    if not roots:
        finding = _scope_finding(
            "SCOPE_EMPTY",
            "Focused publication scope did not resolve any root services.",
            FindingStatus.UNRESOLVED,
            FindingSeverity.WARNING,
        )
        return ScopeBuildOutput(
            None,
            exit_code=1,
            code=finding.code,
            message=finding.message,
        )

    resolved_dependencies = [
        dependency for dependency in analysis.unique_dependencies if dependency.resolved
    ]
    adjacency = _resolved_adjacency(resolved_dependencies)
    membership_state = _traverse_scope(
        roots,
        root_output.root_reason,
        adjacency,
        request.dependency_depth,
    )
    included_services = set(membership_state)
    dependencies = _included_dependencies(resolved_dependencies, included_services)
    boundaries = _scope_boundaries(analysis, included_services, request.dependency_depth)
    document_output = _document_closure(
        analysis,
        included_services,
        selected_process_id=root_output.selected_process_id,
    )
    process_projections = _process_projections(
        analysis,
        included_services,
        boundaries,
        document_output.memberships,
        selected_process_id=root_output.selected_process_id,
    )
    service_memberships = _service_memberships(
        selector.id,
        membership_state,
        services_by_name,
    )
    findings = [*root_output.findings]
    if not included_services:
        findings.append(
            _scope_finding(
                "SCOPE_EMPTY",
                "Focused publication scope did not include any services.",
                FindingStatus.UNRESOLVED,
                FindingSeverity.WARNING,
            )
        )
    if any(boundary.status == ScopeBoundaryStatus.DEPTH_LIMIT for boundary in boundaries):
        findings.append(
            _scope_finding(
                "SCOPE_DEPTH_LIMIT_REACHED",
                "One or more resolved dependencies were stopped by the selected depth.",
                FindingStatus.PARTIALLY_SUPPORTED,
                FindingSeverity.INFO,
            )
        )
    if any(
        boundary.status
        in {
            ScopeBoundaryStatus.UNRESOLVED,
            ScopeBoundaryStatus.OUTSIDE_SNAPSHOT,
            ScopeBoundaryStatus.EXTERNAL_BUILTIN,
        }
        for boundary in boundaries
    ):
        findings.append(
            _scope_finding(
                "SCOPE_BOUNDARY_UNRESOLVED",
                "One or more scope boundaries are unresolved or outside the analyzed snapshot.",
                FindingStatus.UNRESOLVED,
                FindingSeverity.INFO,
            )
        )

    metrics = _scope_metrics(
        request,
        roots,
        service_memberships,
        dependencies,
        boundaries,
        document_output.memberships,
        document_output.boundaries,
        process_projections,
    )
    scope = ScopeResult(
        selector=selector,
        metrics=metrics,
        root_services=[service.identity.full_name for service in roots],
        service_memberships=service_memberships,
        dependencies=dependencies,
        boundaries=boundaries,
        document_memberships=document_output.memberships,
        document_dependencies=document_output.dependencies,
        document_boundaries=document_output.boundaries,
        process_projections=process_projections,
        selected_process_id=root_output.selected_process_id,
        findings=sorted(findings, key=_finding_key),
    )
    return ScopeBuildOutput(scope, exit_code=root_output.exit_code)


def services_for_scope(analysis: AnalysisResult, scope: ScopeResult) -> list[FlowService]:
    included = {membership.service for membership in scope.service_memberships}
    return [
        service
        for service in sorted(
            _all_services(analysis),
            key=lambda item: item.identity.full_name.casefold(),
        )
        if service.identity.full_name in included
    ]


def documents_for_scope(analysis: AnalysisResult, scope: ScopeResult) -> list[DocumentType]:
    included = {membership.document for membership in scope.document_memberships}
    return [
        document
        for document in sorted(
            analysis.document_types, key=lambda item: item.identity.full_name.casefold()
        )
        if document.identity.full_name in included
    ]


def _all_services(analysis: AnalysisResult) -> list[FlowService]:
    return [service for package in analysis.packages for service in package.services]


@dataclass(frozen=True)
class _RootResolution:
    roots: list[FlowService]
    root_reason: ScopeInclusionReason
    selected_process_id: str | None = None
    findings: list[AnalysisFinding] = field(default_factory=list)
    exit_code: int = 0
    error: AnalysisFinding | None = None


def _resolve_roots(
    analysis: AnalysisResult,
    services: list[FlowService],
    services_by_name: dict[str, list[FlowService]],
    request: ScopeRequest,
    *,
    process_catalog_available: bool,
) -> _RootResolution:
    if request.selector_type == ScopeSelectorType.SERVICE:
        targets = services_by_name.get(request.selector_value, [])
        if not targets:
            return _root_error("SCOPE_TARGET_NOT_FOUND", "Target service was not found.")
        if len(targets) > 1:
            return _root_error(
                "SCOPE_TARGET_AMBIGUOUS",
                "Target service matched duplicate canonical service identities.",
            )
        return _RootResolution(
            roots=targets,
            root_reason=ScopeInclusionReason.ROOT_SERVICE,
        )

    if request.selector_type == ScopeSelectorType.NAMESPACE:
        roots = [
            service
            for service in services
            if _namespace_matches(service.identity.namespace, request.selector_value)
        ]
        if not roots:
            return _root_error("SCOPE_TARGET_NOT_FOUND", "Target namespace was not found.")
        duplicate = _duplicate_service_name(roots)
        if duplicate is not None:
            return _root_error(
                "SCOPE_TARGET_AMBIGUOUS",
                f"Target namespace contains duplicate service identity {duplicate!r}.",
            )
        return _RootResolution(
            roots=sorted(roots, key=lambda item: item.identity.full_name.casefold()),
            root_reason=ScopeInclusionReason.ROOT_NAMESPACE_MEMBER,
        )

    if request.selector_type == ScopeSelectorType.PACKAGE:
        packages = [
            package for package in analysis.packages if package.name == request.selector_value
        ]
        if not packages:
            return _root_error("SCOPE_TARGET_NOT_FOUND", "Target package was not found.")
        if len(packages) > 1:
            return _root_error(
                "SCOPE_TARGET_AMBIGUOUS",
                "Target package matched duplicate package identities.",
            )
        roots = list(packages[0].services)
        if not roots:
            return _root_error(
                "SCOPE_EMPTY",
                "Target package contains no executable services to publish.",
            )
        duplicate = _duplicate_service_name(roots)
        if duplicate is not None:
            return _root_error(
                "SCOPE_TARGET_AMBIGUOUS",
                f"Target package contains duplicate service identity {duplicate!r}.",
            )
        return _RootResolution(
            roots=sorted(roots, key=lambda item: item.identity.full_name.casefold()),
            root_reason=ScopeInclusionReason.ROOT_PACKAGE_MEMBER,
        )

    if not process_catalog_available:
        return _root_error(
            "SCOPE_PROCESS_CONFIG_REQUIRED",
            "A process catalog is required when selecting a process scope.",
        )
    if _selected_process_id_has_duplicate_finding(analysis, request.selector_value):
        return _root_error(
            "SCOPE_TARGET_AMBIGUOUS",
            "Target process matched duplicate process definitions.",
        )
    processes_by_id = _multimap(analysis.processes, key=lambda process: process.process_id)
    process_targets = processes_by_id.get(request.selector_value, [])
    if not process_targets:
        return _root_error("SCOPE_TARGET_NOT_FOUND", "Target process was not found.")
    if len(process_targets) > 1:
        return _root_error(
            "SCOPE_TARGET_AMBIGUOUS",
            "Target process matched duplicate process identities.",
        )
    entrypoints = [
        entrypoint
        for entrypoint in analysis.process_entrypoints
        if entrypoint.process_id == request.selector_value
    ]
    resolved = [
        entrypoint
        for entrypoint in entrypoints
        if entrypoint.status == ProcessEntrypointStatus.RESOLVED
        and entrypoint.resolved_service is not None
    ]
    unresolved = [entrypoint for entrypoint in entrypoints if entrypoint not in resolved]
    if not resolved:
        return _root_error(
            "SCOPE_PROCESS_ENTRYPOINT_UNRESOLVED",
            "Target process has no resolved entrypoints to publish.",
        )
    roots = []
    for entrypoint in sorted(
        resolved, key=lambda item: ((item.resolved_service or "").casefold(), item.id)
    ):
        if entrypoint.resolved_service is None:
            continue
        targets_for_entrypoint = services_by_name.get(entrypoint.resolved_service, [])
        if len(targets_for_entrypoint) != 1:
            return _root_error(
                "SCOPE_TARGET_AMBIGUOUS",
                "Resolved process entrypoint no longer maps to one service.",
            )
        if targets_for_entrypoint[0] not in roots:
            roots.append(targets_for_entrypoint[0])
    findings = []
    exit_code = 0
    if unresolved:
        findings.append(
            _scope_finding(
                "SCOPE_PROCESS_ENTRYPOINT_UNRESOLVED",
                "One or more selected process entrypoints were not resolved.",
                FindingStatus.UNRESOLVED,
                FindingSeverity.WARNING,
            )
        )
        exit_code = 1
    return _RootResolution(
        roots=roots,
        root_reason=ScopeInclusionReason.ROOT_PROCESS_ENTRYPOINT,
        selected_process_id=request.selector_value,
        findings=findings,
        exit_code=exit_code,
    )


def _root_error(code: str, message: str) -> _RootResolution:
    return _RootResolution(
        roots=[],
        root_reason=ScopeInclusionReason.ROOT_SERVICE,
        error=_scope_finding(code, message, FindingStatus.UNRESOLVED, FindingSeverity.ERROR),
    )


def _selected_process_id_has_duplicate_finding(
    analysis: AnalysisResult, process_id: str
) -> bool:
    expected_prefix = f"Duplicate process id {process_id!r};"
    return any(
        finding.code == "PROCESS_ID_DUPLICATE"
        and finding.source.artifact_type == "process_catalog"
        and finding.message.startswith(expected_prefix)
        for finding in analysis.findings
    )


def _resolved_adjacency(
    resolved_dependencies: list[UniqueDependency],
) -> dict[str, list[UniqueDependency]]:
    adjacency: dict[str, list[UniqueDependency]] = defaultdict(list)
    for dependency in resolved_dependencies:
        adjacency[dependency.source_service].append(dependency)
    return {
        source: sorted(items, key=_dependency_traversal_key)
        for source, items in adjacency.items()
    }


def _traverse_scope(
    roots: list[FlowService],
    root_reason: ScopeInclusionReason,
    adjacency: dict[str, list[UniqueDependency]],
    depth_limit: int | None,
) -> dict[str, _MembershipState]:
    root_names = [service.identity.full_name for service in sorted(roots, key=_service_key)]
    states: dict[str, _MembershipState] = {}
    best_seen: dict[tuple[str, str], tuple[int, tuple[str, ...]]] = {}
    queue = deque[tuple[str, str, int, tuple[str, ...]]]()
    for root_name in root_names:
        queue.append((root_name, root_name, 0, ()))

    while queue:
        root_name, service_name, depth, path = queue.popleft()
        seen_key = (root_name, service_name)
        previous = best_seen.get(seen_key)
        if previous is not None and (previous[0], previous[1]) <= (depth, path):
            continue
        best_seen[seen_key] = (depth, path)
        state = states.get(service_name)
        if state is None:
            reasons = {root_reason} if service_name == root_name else set()
            if service_name != root_name:
                reasons.add(
                    ScopeInclusionReason.DIRECT_DEPENDENCY
                    if depth == 1
                    else ScopeInclusionReason.TRANSITIVE_DEPENDENCY
                )
            states[service_name] = _MembershipState(
                minimum_depth=depth,
                paths_by_root={root_name: path},
                reasons=reasons,
            )
        else:
            state.paths_by_root[root_name] = path
            if service_name == root_name:
                state.reasons.add(root_reason)
            elif depth == 1:
                state.reasons.add(ScopeInclusionReason.DIRECT_DEPENDENCY)
            else:
                state.reasons.add(ScopeInclusionReason.TRANSITIVE_DEPENDENCY)
            if depth < state.minimum_depth:
                state.minimum_depth = depth

        if depth_limit is not None and depth >= depth_limit:
            continue
        for dependency in adjacency.get(service_name, []):
            queue.append(
                (
                    root_name,
                    dependency.target_service,
                    depth + 1,
                    (*path, dependency.id),
                )
            )
    return states


def _service_memberships(
    selector_id: str,
    membership_state: dict[str, _MembershipState],
    services_by_name: dict[str, list[FlowService]],
) -> list[ScopeServiceMembership]:
    memberships: list[ScopeServiceMembership] = []
    for service_name, state in sorted(
        membership_state.items(), key=lambda item: (item[1].minimum_depth, item[0].casefold())
    ):
        service = services_by_name[service_name][0]
        roots = sorted(state.paths_by_root, key=str.casefold)
        path_samples = [
            ScopeRepresentativePathSample(
                root_service=root,
                dependency_ids=list(state.paths_by_root[root]),
            )
            for root in roots[:MAX_REPRESENTATIVE_PATH_SAMPLES]
        ]
        memberships.append(
            ScopeServiceMembership(
                id=_stable_id("scope_member", selector_id, service_name),
                selector_id=selector_id,
                service=service_name,
                service_id=_stable_id("service", service_name),
                service_type=service.service_type,
                analysis_status=service.analysis_status,
                is_root=any(path == () for path in state.paths_by_root.values()),
                minimum_depth=state.minimum_depth,
                inclusion_reasons=sorted(state.reasons, key=lambda item: item.value),
                reaching_root_count=len(roots),
                reaching_root_samples=roots[:MAX_REACHING_ROOT_SAMPLES],
                reaching_root_samples_omitted=max(0, len(roots) - MAX_REACHING_ROOT_SAMPLES),
                representative_path_samples=path_samples,
                representative_path_samples_omitted=max(
                    0, len(roots) - MAX_REPRESENTATIVE_PATH_SAMPLES
                ),
            )
        )
    return memberships


def _included_dependencies(
    resolved_dependencies: list[UniqueDependency],
    included_services: set[str],
) -> list[ScopeDependencyEdge]:
    edges: list[ScopeDependencyEdge] = []
    for dependency in sorted(resolved_dependencies, key=_process_edge_key):
        if dependency.source_service not in included_services:
            continue
        if dependency.target_service not in included_services:
            continue
        edges.append(
            ScopeDependencyEdge(
                id=_stable_id("scope_edge", dependency.id),
                dependency_id=dependency.id,
                source_service=dependency.source_service,
                target_service=dependency.target_service,
                dependency_kind=dependency.dependency_kind,
                occurrence_count=dependency.occurrence_count,
            )
        )
    return edges


def _scope_boundaries(
    analysis: AnalysisResult,
    included_services: set[str],
    depth_limit: int | None,
) -> list[ScopeBoundary]:
    grouped: dict[tuple[str, str, str, str, ScopeBoundaryStatus], _BoundaryAccumulator] = {}
    for dependency in sorted(analysis.unique_dependencies, key=_process_edge_key):
        if dependency.source_service not in included_services:
            continue
        if dependency.resolved and dependency.target_service not in included_services:
            if depth_limit is not None:
                _add_boundary(
                    grouped,
                    dependency.source_service,
                    dependency.target_service,
                    "service",
                    dependency.dependency_kind.value,
                    ScopeBoundaryStatus.DEPTH_LIMIT,
                    dependency.occurrence_count,
                    [dependency.id],
                    dependency.source_samples,
                )
            continue
        if dependency.resolved:
            continue
        status = _unresolved_dependency_status(dependency.target_service)
        _add_boundary(
            grouped,
            dependency.source_service,
            dependency.target_service,
            "service_target",
            dependency.dependency_kind.value,
            status,
            dependency.occurrence_count,
            [dependency.id],
            dependency.source_samples,
        )

    for invocation in analysis.java_invocation_occurrences:
        if invocation.caller not in included_services:
            continue
        if invocation.resolved and invocation.canonical_target in included_services:
            continue
        if invocation.target_status == JavaInvocationTargetStatus.STATIC_TARGET:
            continue
        status = (
            ScopeBoundaryStatus.UNRESOLVED
            if invocation.target_status == JavaInvocationTargetStatus.MALFORMED_TARGET
            else ScopeBoundaryStatus.DYNAMIC
        )
        target = (
            invocation.canonical_target
            or invocation.declared_target
            or "<dynamic-java-target>"
        )
        _add_boundary(
            grouped,
            invocation.caller,
            target,
            "java_invocation",
            "JAVA_INVOKE",
            status,
            1,
            [invocation.id],
            [invocation.source.primary],
        )

    for service in _all_services(analysis):
        if service.identity.full_name not in included_services:
            continue
        for finding in service.findings:
            finding_status = _finding_boundary_status(finding)
            if finding_status is None:
                continue
            _add_boundary(
                grouped,
                service.identity.full_name,
                _finding_boundary_target(finding, finding_status),
                "finding",
                "CALL_LIKE_FINDING",
                finding_status,
                finding.occurrence_count,
                [finding.code],
                [finding.source, *finding.sample_source_references],
            )
    boundaries = [
        accumulator.to_boundary()
        for _, accumulator in sorted(grouped.items(), key=lambda item: item[0])
    ]
    return boundaries


@dataclass
class _BoundaryAccumulator:
    source_service: str
    target: str
    target_category: str
    dependency_or_call_kind: str
    status: ScopeBoundaryStatus
    occurrence_count: int = 0
    evidence_ids: set[str] = field(default_factory=set)
    source_samples: list[SourceReference] = field(default_factory=list)

    def to_boundary(self) -> ScopeBoundary:
        return ScopeBoundary(
            id=_stable_id(
                "scope_boundary",
                self.source_service,
                self.target,
                self.target_category,
                self.dependency_or_call_kind,
                self.status.value,
            ),
            source_service=self.source_service,
            target=self.target,
            target_category=self.target_category,
            dependency_or_call_kind=self.dependency_or_call_kind,
            status=self.status,
            occurrence_count=self.occurrence_count,
            evidence_ids=sorted(self.evidence_ids),
            source_samples=_bounded_sources(self.source_samples),
        )


def _add_boundary(
    grouped: dict[tuple[str, str, str, str, ScopeBoundaryStatus], _BoundaryAccumulator],
    source_service: str,
    target: str,
    target_category: str,
    dependency_or_call_kind: str,
    status: ScopeBoundaryStatus,
    occurrence_count: int,
    evidence_ids: list[str],
    source_samples: list[SourceReference],
) -> None:
    key = (source_service, target, target_category, dependency_or_call_kind, status)
    accumulator = grouped.get(key)
    if accumulator is None:
        accumulator = _BoundaryAccumulator(
            source_service=source_service,
            target=target,
            target_category=target_category,
            dependency_or_call_kind=dependency_or_call_kind,
            status=status,
        )
        grouped[key] = accumulator
    accumulator.occurrence_count += occurrence_count
    accumulator.evidence_ids.update(evidence_ids)
    accumulator.source_samples.extend(source_samples)


@dataclass(frozen=True)
class _DocumentClosureOutput:
    memberships: list[ScopeDocumentMembership]
    dependencies: list[ScopeDocumentDependencyEdge]
    boundaries: list[ScopeDocumentBoundary]


def _document_closure(
    analysis: AnalysisResult,
    included_services: set[str],
    *,
    selected_process_id: str | None,
) -> _DocumentClosureOutput:
    document_names = {document.identity.full_name for document in analysis.document_types}
    state: dict[str, _DocumentState] = {}
    queue = deque[tuple[str, int]]()
    boundaries: list[ScopeDocumentBoundary] = []

    for service_dependency in sorted(
        analysis.service_document_dependencies, key=_service_document_dependency_key
    ):
        if service_dependency.service not in included_services:
            continue
        if (
            not service_dependency.resolved
            or service_dependency.target_document not in document_names
        ):
            boundaries.append(
                ScopeDocumentBoundary(
                    id=_stable_id("scope_doc_boundary", service_dependency.id),
                    source=service_dependency.service,
                    target_document=service_dependency.target_document,
                    status=ScopeBoundaryStatus.UNRESOLVED,
                    occurrence_count=service_dependency.occurrence_count,
                    evidence_ids=[service_dependency.id],
                    source_samples=_bounded_sources(service_dependency.source_samples),
                )
            )
            continue
        doc_state = state.setdefault(service_dependency.target_document, _DocumentState(0))
        doc_state.reasons.add(ScopeDocumentInclusionReason.DIRECT_SERVICE_DOCUMENT)
        doc_state.source_services.add(service_dependency.service)
        queue.append((service_dependency.target_document, 0))

    if selected_process_id is not None:
        for relationship in sorted(
            analysis.process_document_relationships,
            key=lambda item: (
                item.process_id.casefold(),
                item.target_document.casefold(),
                item.id,
            ),
        ):
            if relationship.process_id != selected_process_id:
                continue
            if not relationship.resolved or relationship.target_document not in document_names:
                boundaries.append(
                    ScopeDocumentBoundary(
                        id=_stable_id("scope_doc_boundary", relationship.id),
                        source=relationship.service
                        or relationship.source_document
                        or selected_process_id,
                        target_document=relationship.target_document,
                        status=ScopeBoundaryStatus.UNRESOLVED,
                        occurrence_count=relationship.occurrence_count,
                        evidence_ids=[relationship.id],
                    )
                )
                continue
            doc_state = state.setdefault(relationship.target_document, _DocumentState(0))
            doc_state.reasons.add(ScopeDocumentInclusionReason.DIRECT_PROCESS_DOCUMENT)
            doc_state.source_processes.add(selected_process_id)
            queue.append((relationship.target_document, 0))

    document_dependencies_by_source: dict[str, list[DocumentDependency]] = defaultdict(list)
    for dependency in analysis.document_dependencies:
        document_dependencies_by_source[dependency.source_document].append(dependency)
    for source in document_dependencies_by_source:
        document_dependencies_by_source[source] = sorted(
            document_dependencies_by_source[source], key=_document_dependency_key
        )

    included_dependency_edges: dict[str, ScopeDocumentDependencyEdge] = {}
    visited_depth: dict[str, int] = {}
    while queue:
        document_name, depth = queue.popleft()
        previous_depth = visited_depth.get(document_name)
        if previous_depth is not None and previous_depth <= depth:
            continue
        visited_depth[document_name] = depth
        doc_state = state.setdefault(document_name, _DocumentState(depth))
        if depth < doc_state.minimum_document_depth:
            doc_state.minimum_document_depth = depth
        for document_dependency in document_dependencies_by_source.get(document_name, []):
            if (
                document_dependency.resolved
                and document_dependency.target_document in document_names
            ):
                included_dependency_edges[document_dependency.id] = (
                    ScopeDocumentDependencyEdge(
                        id=_stable_id("scope_doc_edge", document_dependency.id),
                        dependency_id=document_dependency.id,
                        source_document=document_dependency.source_document,
                        target_document=document_dependency.target_document,
                        occurrence_count=document_dependency.occurrence_count,
                    )
                )
                target_state = state.setdefault(
                    document_dependency.target_document, _DocumentState(depth + 1)
                )
                target_state.reasons.add(ScopeDocumentInclusionReason.TRANSITIVE_DOCUMENT)
                if depth + 1 < target_state.minimum_document_depth:
                    target_state.minimum_document_depth = depth + 1
                queue.append((document_dependency.target_document, depth + 1))
            else:
                boundaries.append(
                    ScopeDocumentBoundary(
                        id=_stable_id("scope_doc_boundary", document_dependency.id),
                        source=document_dependency.source_document,
                        target_document=document_dependency.target_document,
                        status=ScopeBoundaryStatus.UNRESOLVED,
                        occurrence_count=document_dependency.occurrence_count,
                        evidence_ids=[document_dependency.id],
                        source_samples=_bounded_sources(document_dependency.source_samples),
                    )
                )

    memberships = [
        ScopeDocumentMembership(
            id=_stable_id("scope_doc_member", document_name),
            document=document_name,
            inclusion_reasons=sorted(doc_state.reasons, key=lambda item: item.value),
            direct=any(
                reason
                in {
                    ScopeDocumentInclusionReason.DIRECT_SERVICE_DOCUMENT,
                    ScopeDocumentInclusionReason.DIRECT_PROCESS_DOCUMENT,
                }
                for reason in doc_state.reasons
            ),
            minimum_document_depth=doc_state.minimum_document_depth,
            source_services=sorted(doc_state.source_services, key=str.casefold),
            source_processes=sorted(doc_state.source_processes, key=str.casefold),
        )
        for document_name, doc_state in sorted(state.items(), key=lambda item: item[0].casefold())
        if document_name in document_names
    ]
    return _DocumentClosureOutput(
        memberships=memberships,
        dependencies=sorted(
            included_dependency_edges.values(),
            key=lambda item: (
                item.source_document.casefold(),
                item.target_document.casefold(),
                item.id,
            ),
        ),
        boundaries=sorted(
            boundaries,
            key=lambda item: (item.source.casefold(), item.target_document.casefold(), item.id),
        ),
    )


@dataclass
class _DocumentState:
    minimum_document_depth: int
    reasons: set[ScopeDocumentInclusionReason] = field(default_factory=set)
    source_services: set[str] = field(default_factory=set)
    source_processes: set[str] = field(default_factory=set)


def _process_projections(
    analysis: AnalysisResult,
    included_services: set[str],
    boundaries: list[ScopeBoundary],
    document_memberships: list[ScopeDocumentMembership],
    *,
    selected_process_id: str | None,
) -> list[ScopeProcessProjection]:
    if selected_process_id is None:
        return []
    process = next(
        (item for item in analysis.processes if item.process_id == selected_process_id),
        None,
    )
    if process is None:
        return []
    memberships = [
        membership
        for membership in analysis.process_service_memberships
        if membership.process_id == selected_process_id
    ]
    edges = [
        edge
        for edge in analysis.process_dependency_edges
        if edge.process_id == selected_process_id
    ]
    unresolved = [
        call
        for call in analysis.process_unresolved_calls
        if call.process_id == selected_process_id
    ]
    relationships = [
        relationship
        for relationship in analysis.process_document_relationships
        if relationship.process_id == selected_process_id
    ]
    entrypoints = [
        entrypoint
        for entrypoint in analysis.process_entrypoints
        if entrypoint.process_id == selected_process_id
    ]
    published_members = {membership.service for membership in memberships} & included_services
    published_edges = [
        edge
        for edge in edges
        if edge.source_service in published_members and edge.target_service in published_members
    ]
    published_unresolved = [
        call for call in unresolved if call.source_service in published_members
    ]
    boundary_count = sum(
        1 for boundary in boundaries if boundary.source_service in published_members
    )
    return [
        ScopeProcessProjection(
            process_id=process.process_id,
            process_name=process.name,
            full_member_count=len(memberships),
            published_member_count=len(published_members),
            full_edge_count=len(edges),
            published_edge_count=len(published_edges),
            boundary_dependency_count=boundary_count,
            full_unresolved_call_count=len(unresolved),
            published_unresolved_call_count=len(published_unresolved),
            full_document_relationship_count=len(relationships),
            published_document_count=len(document_memberships),
            entrypoint_count=len(entrypoints),
            resolved_entrypoint_count=sum(
                1
                for entrypoint in entrypoints
                if entrypoint.status == ProcessEntrypointStatus.RESOLVED
            ),
        )
    ]


def _scope_metrics(
    request: ScopeRequest,
    roots: list[FlowService],
    memberships: list[ScopeServiceMembership],
    dependencies: list[ScopeDependencyEdge],
    boundaries: list[ScopeBoundary],
    document_memberships: list[ScopeDocumentMembership],
    document_boundaries: list[ScopeDocumentBoundary],
    process_projections: list[ScopeProcessProjection],
) -> ScopeMetrics:
    depth_counts = Counter(str(membership.minimum_depth) for membership in memberships)
    boundary_counts = Counter(boundary.status.value for boundary in boundaries)
    return ScopeMetrics(
        selector_type=request.selector_type,
        selector_value=request.selector_value,
        dependency_depth=request.depth_label,
        roots_resolved=len(roots),
        services_included=len(memberships),
        root_services_included=sum(1 for membership in memberships if membership.is_root),
        services_by_minimum_depth=dict(sorted(depth_counts.items(), key=lambda item: int(item[0]))),
        included_resolved_dependencies=len(dependencies),
        boundary_dependencies=len(boundaries),
        boundary_counts_by_status=dict(sorted(boundary_counts.items())),
        documents_included=len(document_memberships),
        direct_documents_included=sum(
            1 for membership in document_memberships if membership.direct
        ),
        transitive_documents_included=sum(
            1 for membership in document_memberships if not membership.direct
        ),
        document_boundaries=len(document_boundaries),
        processes_published=len(process_projections),
        maximum_reached_depth=max(
            (membership.minimum_depth for membership in memberships), default=0
        ),
        reaching_root_samples_omitted=sum(
            membership.reaching_root_samples_omitted for membership in memberships
        ),
        representative_path_samples_omitted=sum(
            membership.representative_path_samples_omitted for membership in memberships
        ),
    )


def _unresolved_dependency_status(target: str) -> ScopeBoundaryStatus:
    folded = target.casefold()
    if folded.startswith("pub.") or folded.startswith("wm."):
        return ScopeBoundaryStatus.EXTERNAL_BUILTIN
    if _valid_service_full_name(target):
        return ScopeBoundaryStatus.OUTSIDE_SNAPSHOT
    return ScopeBoundaryStatus.UNRESOLVED


def _finding_boundary_status(finding: AnalysisFinding) -> ScopeBoundaryStatus | None:
    code = finding.code.upper()
    message = finding.message.upper()
    if "DYNAMIC" in code and ("SERVICE" in code or "INVOKE" in code or "CALL" in code):
        return ScopeBoundaryStatus.DYNAMIC
    if "UNSUPPORTED" in code and ("SERVICE" in code or "INVOKE" in code or "CALL" in code):
        return ScopeBoundaryStatus.UNSUPPORTED
    if "PARTIALLY_STATIC_SERVICE_TARGET" in code:
        return ScopeBoundaryStatus.DYNAMIC
    if "DYNAMIC" in message and ("SERVICE" in message or "INVOK" in message):
        return ScopeBoundaryStatus.DYNAMIC
    return None


def _finding_boundary_target(
    finding: AnalysisFinding, status: ScopeBoundaryStatus
) -> str:
    if status == ScopeBoundaryStatus.DYNAMIC:
        return "<dynamic-target>"
    if status == ScopeBoundaryStatus.UNSUPPORTED:
        return "<unsupported-call-like-construct>"
    return "<unresolved-target>"


def _valid_service_full_name(value: str) -> bool:
    if CONTROL_RE.search(value) or value.count(":") != 1:
        return False
    namespace, service = value.split(":", 1)
    return _valid_namespace(namespace) and _valid_name_segment(service)


def _valid_namespace(value: str) -> bool:
    if not value or CONTROL_RE.search(value):
        return False
    if any(char in value for char in "/\\:"):
        return False
    return all(_valid_name_segment(segment) for segment in value.split("."))


def _valid_name_segment(value: str) -> bool:
    return bool(value) and NAMESPACE_SEGMENT_RE.match(value) is not None


def _valid_package_name(value: str) -> bool:
    if not value or CONTROL_RE.search(value):
        return False
    if any(char in value for char in "/\\"):
        return False
    return value not in {".", ".."} and ":" not in value


def _valid_process_id(value: str) -> bool:
    if not value or CONTROL_RE.search(value):
        return False
    if any(char in value for char in "/\\") or ".." in value:
        return False
    if value.startswith(".") or value.endswith("."):
        return False
    return PROCESS_ID_RE.match(value) is not None


def _namespace_matches(namespace: str, prefix: str) -> bool:
    return namespace == prefix or namespace.startswith(f"{prefix}.")


def _duplicate_service_name(services: list[FlowService]) -> str | None:
    counts = Counter(service.identity.full_name for service in services)
    duplicate_names = sorted(name for name, count in counts.items() if count > 1)
    return duplicate_names[0] if duplicate_names else None


def _multimap[T](items: list[T], *, key: Callable[[T], str]) -> dict[str, list[T]]:
    output: dict[str, list[T]] = defaultdict(list)
    for item in items:
        output[key(item)].append(item)
    return dict(output)


def _bounded_sources(sources: list[SourceReference]) -> list[SourceReference]:
    seen: set[tuple[str, str | None, str | None, int | None]] = set()
    output: list[SourceReference] = []
    for source in sources:
        key = (
            source.path,
            source.artifact_type,
            source.source_node or source.xml_path,
            source.line,
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(source)
        if len(output) >= MAX_SOURCE_SAMPLES:
            break
    return output


def _service_key(service: FlowService) -> tuple[str, str]:
    return (service.identity.full_name.casefold(), service.identity.full_name)


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


def _scope_finding(
    code: str,
    message: str,
    status: FindingStatus,
    severity: FindingSeverity,
) -> AnalysisFinding:
    return AnalysisFinding(
        status=status,
        code=code,
        message=message,
        severity=severity,
        source=SourceReference(path="<cli>", artifact_type="focused_publication_scope"),
    )


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"
