from __future__ import annotations

import hashlib
from pathlib import Path

from wm_doc.ir import (
    AnalysisResult,
    DocumentDependency,
    ProcessDefinition,
    ProcessUnresolvedCall,
)
from wm_doc.scope_analysis import ScopeResult


def render_dependency_dot(analysis: AnalysisResult) -> str:
    analyzed = {
        service.identity.full_name: service.service_type.value.lower()
        for package in analysis.packages
        for service in package.services
    }
    targets = {dependency.target_service for dependency in analysis.unique_dependencies}
    nodes = sorted(set(analyzed) | targets, key=str.casefold)
    lines = ["digraph dependencies {", "  rankdir=LR;"]
    for node in nodes:
        attrs = [f'label="{_escape(node)}"']
        if node in analyzed:
            attrs.append(f'kind="{analyzed[node]}_service"')
        else:
            attrs.append('kind="dependency_target"')
        lines.append(f"  {_node_id(node)} [{', '.join(attrs)}];")
    for dependency in sorted(
        analysis.unique_dependencies,
        key=lambda item: (
            item.source_service.casefold(),
            item.dependency_kind.value,
            item.target_service.casefold(),
        ),
    ):
        attrs = [
            f'label="{dependency.dependency_kind.value}"',
            f'kind="{dependency.dependency_kind.value}"',
            f'occurrences="{dependency.occurrence_count}"',
            f'resolved="{str(dependency.resolved).lower()}"',
        ]
        lines.append(
            f"  {_node_id(dependency.source_service)} -> {_node_id(dependency.target_service)} "
            f"[{', '.join(attrs)}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_dependency_dot(output_dir: Path, analysis: AnalysisResult) -> Path:
    graph_dir = output_dir / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    path = graph_dir / "dependencies.dot"
    path.write_text(render_dependency_dot(analysis), encoding="utf-8")
    return path


def render_document_dot(analysis: AnalysisResult) -> str:
    local_documents = {document.identity.full_name for document in analysis.document_types}
    targets = {dependency.target_document for dependency in analysis.document_dependencies}
    sources = {dependency.source_document for dependency in analysis.document_dependencies}
    nodes = sorted(local_documents | targets | sources, key=str.casefold)
    lines = ["digraph documents {", "  rankdir=LR;"]
    for node in nodes:
        attrs = [f'label="{_escape(node)}"']
        if node in local_documents:
            attrs.append('kind="document_type"')
        else:
            attrs.append('kind="unresolved_document"')
        lines.append(f"  {_node_id(node)} [{', '.join(attrs)}];")
    for dependency in sorted(analysis.document_dependencies, key=_document_dependency_key):
        attrs = [
            f'label="{dependency.dependency_kind.value}"',
            f'kind="{dependency.dependency_kind.value}"',
            f'occurrences="{dependency.occurrence_count}"',
            f'resolved="{str(dependency.resolved).lower()}"',
        ]
        lines.append(
            f"  {_node_id(dependency.source_document)} -> {_node_id(dependency.target_document)} "
            f"[{', '.join(attrs)}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_document_dot(output_dir: Path, analysis: AnalysisResult) -> Path:
    graph_dir = output_dir / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    path = graph_dir / "documents.dot"
    path.write_text(render_document_dot(analysis), encoding="utf-8")
    return path


def render_process_dot(analysis: AnalysisResult, process: ProcessDefinition) -> str:
    services = {
        service.identity.full_name: service
        for package in analysis.packages
        for service in package.services
    }
    memberships = [
        membership
        for membership in analysis.process_service_memberships
        if membership.process_id == process.process_id
    ]
    member_names = {membership.service for membership in memberships}
    entrypoints = {membership.service for membership in memberships if membership.entrypoint}
    unresolved_calls = [
        call
        for call in analysis.process_unresolved_calls
        if call.process_id == process.process_id
    ]
    lines = ["digraph process {", "  rankdir=LR;"]
    for service_name in sorted(member_names, key=str.casefold):
        service = services.get(service_name)
        kind = (
            f"{service.service_type.value.lower()}_service"
            if service is not None
            else "service"
        )
        attrs = [f'label="{_escape(service_name)}"', f'kind="{kind}"']
        if service_name in entrypoints:
            attrs.append('entrypoint="true"')
            attrs.append('shape="box"')
        if service is not None and service.analysis_status.value == "OPAQUE":
            attrs.append('style="dashed"')
        lines.append(f"  {_node_id(service_name)} [{', '.join(attrs)}];")
    for call in unresolved_calls:
        unresolved_id = _process_unresolved_node_key(call)
        attrs = [f'label="{_escape(call.target_service)}"', 'kind="unresolved_target"']
        lines.append(f"  {_node_id(unresolved_id)} [{', '.join(attrs)}];")
    for edge in sorted(
        [
            edge
            for edge in analysis.process_dependency_edges
            if edge.process_id == process.process_id
        ],
        key=lambda item: (
            item.source_service.casefold(),
            item.target_service.casefold(),
            item.dependency_kind.value,
            item.id,
        ),
    ):
        attrs = [
            f'label="{edge.dependency_kind.value}"',
            f'kind="{edge.dependency_kind.value}"',
            f'occurrences="{edge.occurrence_count}"',
        ]
        lines.append(
            f"  {_node_id(edge.source_service)} -> {_node_id(edge.target_service)} "
            f"[{', '.join(attrs)}];"
        )
    for call in unresolved_calls:
        unresolved_id = _process_unresolved_node_key(call)
        attrs = [
            f'label="{call.dependency_kind.value}"',
            f'kind="{call.dependency_kind.value}"',
            f'occurrences="{call.occurrence_count}"',
            'resolved="false"',
        ]
        lines.append(
            f"  {_node_id(call.source_service)} -> {_node_id(unresolved_id)} "
            f"[{', '.join(attrs)}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_process_dots(output_dir: Path, analysis: AnalysisResult) -> list[Path]:
    if not analysis.processes:
        return []
    graph_dir = output_dir / "graphs" / "processes"
    graph_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for process in sorted(analysis.processes, key=lambda item: item.process_id.casefold()):
        path = graph_dir / f"{process.process_id}.dot"
        path.write_text(render_process_dot(analysis, process), encoding="utf-8")
        paths.append(path)
    return paths


def render_scope_dot(scope: ScopeResult) -> str:
    services = {membership.service: membership for membership in scope.service_memberships}
    lines = ["digraph scope {", "  rankdir=LR;"]
    for service_name, membership in sorted(services.items(), key=lambda item: item[0].casefold()):
        attrs = [
            f'label="{_escape(service_name)}"',
            f'kind="{membership.service_type.value.lower()}_service"',
            f'analysis_status="{membership.analysis_status.value}"',
            f'root="{str(membership.is_root).lower()}"',
            f'depth="{membership.minimum_depth}"',
        ]
        if membership.is_root:
            attrs.append('shape="box"')
        if membership.analysis_status.value == "OPAQUE":
            attrs.append('style="dashed"')
        lines.append(f"  {_node_id(service_name)} [{', '.join(attrs)}];")
    for boundary in sorted(
        scope.boundaries,
        key=lambda item: (
            item.source_service.casefold(),
            item.status.value,
            item.target.casefold(),
            item.id,
        ),
    ):
        boundary_node = _scope_boundary_node_key(boundary.id)
        attrs = [
            f'label="{_escape(boundary.status.value + ": " + boundary.target)}"',
            'kind="scope_boundary"',
            f'status="{boundary.status.value}"',
        ]
        lines.append(f"  {_node_id(boundary_node)} [{', '.join(attrs)}];")
    for dependency in sorted(
        scope.dependencies,
        key=lambda item: (
            item.source_service.casefold(),
            item.target_service.casefold(),
            item.dependency_kind.value,
            item.id,
        ),
    ):
        attrs = [
            f'label="{dependency.dependency_kind.value}"',
            f'kind="{dependency.dependency_kind.value}"',
            f'occurrences="{dependency.occurrence_count}"',
            'resolved="true"',
        ]
        lines.append(
            f"  {_node_id(dependency.source_service)} -> {_node_id(dependency.target_service)} "
            f"[{', '.join(attrs)}];"
        )
    for boundary in sorted(
        scope.boundaries,
        key=lambda item: (
            item.source_service.casefold(),
            item.status.value,
            item.target.casefold(),
            item.id,
        ),
    ):
        boundary_node = _scope_boundary_node_key(boundary.id)
        attrs = [
            f'label="{_escape(boundary.dependency_or_call_kind)}"',
            f'kind="{_escape(boundary.dependency_or_call_kind)}"',
            f'status="{boundary.status.value}"',
            f'occurrences="{boundary.occurrence_count}"',
            'resolved="false"',
        ]
        lines.append(
            f"  {_node_id(boundary.source_service)} -> {_node_id(boundary_node)} "
            f"[{', '.join(attrs)}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_scope_dot(output_dir: Path, scope: ScopeResult) -> Path:
    graph_dir = output_dir / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    path = graph_dir / "scope.dot"
    path.write_text(render_scope_dot(scope), encoding="utf-8")
    return path


def render_scope_document_dot(scope: ScopeResult) -> str:
    documents = {membership.document for membership in scope.document_memberships}
    lines = ["digraph scope_documents {", "  rankdir=LR;"]
    for document in sorted(documents, key=str.casefold):
        attrs = [f'label="{_escape(document)}"', 'kind="document_type"']
        lines.append(f"  {_node_id(document)} [{', '.join(attrs)}];")
    for boundary in sorted(
        scope.document_boundaries,
        key=lambda item: (item.source.casefold(), item.target_document.casefold(), item.id),
    ):
        boundary_key = _scope_boundary_node_key(boundary.id)
        attrs = [
            f'label="{_escape(boundary.status.value + ": " + boundary.target_document)}"',
            'kind="document_boundary"',
            f'status="{boundary.status.value}"',
        ]
        lines.append(f"  {_node_id(boundary_key)} [{', '.join(attrs)}];")
    for dependency in sorted(
        scope.document_dependencies,
        key=lambda item: (
            item.source_document.casefold(),
            item.target_document.casefold(),
            item.id,
        ),
    ):
        attrs = [
            'label="REFERENCES_DOCUMENT"',
            'kind="REFERENCES_DOCUMENT"',
            f'occurrences="{dependency.occurrence_count}"',
            'resolved="true"',
        ]
        lines.append(
            f"  {_node_id(dependency.source_document)} -> {_node_id(dependency.target_document)} "
            f"[{', '.join(attrs)}];"
        )
    for boundary in sorted(
        scope.document_boundaries,
        key=lambda item: (item.source.casefold(), item.target_document.casefold(), item.id),
    ):
        if boundary.source not in documents:
            continue
        attrs = [
            'label="UNRESOLVED_DOCUMENT_REFERENCE"',
            'kind="UNRESOLVED_DOCUMENT_REFERENCE"',
            f'status="{boundary.status.value}"',
            f'occurrences="{boundary.occurrence_count}"',
            'resolved="false"',
        ]
        lines.append(
            f"  {_node_id(boundary.source)} -> {_node_id(_scope_boundary_node_key(boundary.id))} "
            f"[{', '.join(attrs)}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_scope_document_dot(output_dir: Path, scope: ScopeResult) -> Path | None:
    if not scope.document_dependencies and not any(
        boundary.source in {membership.document for membership in scope.document_memberships}
        for boundary in scope.document_boundaries
    ):
        return None
    graph_dir = output_dir / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    path = graph_dir / "scope-documents.dot"
    path.write_text(render_scope_document_dot(scope), encoding="utf-8")
    return path


def render_scoped_process_dot(scope: ScopeResult) -> str:
    lines = ["digraph process_scope {", "  rankdir=LR;"]
    process_id = scope.selected_process_id or "process"
    for membership in sorted(
        scope.service_memberships, key=lambda item: item.service.casefold()
    ):
        attrs = [
            f'label="{_escape(membership.service)}"',
            f'kind="{membership.service_type.value.lower()}_service"',
            f'analysis_status="{membership.analysis_status.value}"',
            f'entrypoint="{str(membership.is_root).lower()}"',
        ]
        if membership.is_root:
            attrs.append('shape="box"')
        if membership.analysis_status.value == "OPAQUE":
            attrs.append('style="dashed"')
        lines.append(f"  {_node_id(membership.service)} [{', '.join(attrs)}];")
    for boundary in sorted(
        scope.boundaries,
        key=lambda item: (
            item.source_service.casefold(),
            item.status.value,
            item.target.casefold(),
            item.id,
        ),
    ):
        boundary_node = _scope_boundary_node_key(f"{process_id}\0{boundary.id}")
        attrs = [
            f'label="{_escape(boundary.status.value + ": " + boundary.target)}"',
            'kind="scope_boundary"',
            f'status="{boundary.status.value}"',
        ]
        lines.append(f"  {_node_id(boundary_node)} [{', '.join(attrs)}];")
    for dependency in sorted(
        scope.dependencies,
        key=lambda item: (
            item.source_service.casefold(),
            item.target_service.casefold(),
            item.dependency_kind.value,
            item.id,
        ),
    ):
        attrs = [
            f'label="{dependency.dependency_kind.value}"',
            f'kind="{dependency.dependency_kind.value}"',
            f'occurrences="{dependency.occurrence_count}"',
        ]
        lines.append(
            f"  {_node_id(dependency.source_service)} -> {_node_id(dependency.target_service)} "
            f"[{', '.join(attrs)}];"
        )
    for boundary in sorted(
        scope.boundaries,
        key=lambda item: (
            item.source_service.casefold(),
            item.status.value,
            item.target.casefold(),
            item.id,
        ),
    ):
        boundary_node = _scope_boundary_node_key(f"{process_id}\0{boundary.id}")
        attrs = [
            f'label="{_escape(boundary.dependency_or_call_kind)}"',
            f'kind="{_escape(boundary.dependency_or_call_kind)}"',
            f'status="{boundary.status.value}"',
            f'occurrences="{boundary.occurrence_count}"',
            'resolved="false"',
        ]
        lines.append(
            f"  {_node_id(boundary.source_service)} -> {_node_id(boundary_node)} "
            f"[{', '.join(attrs)}];"
        )
    lines.append("}")
    return "\n".join(lines) + "\n"


def write_scoped_process_dot(output_dir: Path, scope: ScopeResult) -> Path | None:
    if scope.selected_process_id is None:
        return None
    graph_dir = output_dir / "graphs" / "processes"
    graph_dir.mkdir(parents=True, exist_ok=True)
    path = graph_dir / f"{scope.selected_process_id}.dot"
    path.write_text(render_scoped_process_dot(scope), encoding="utf-8")
    return path


def _document_dependency_key(dependency: DocumentDependency) -> tuple[str, str, str]:
    return (
        dependency.source_document.casefold(),
        dependency.target_document.casefold(),
        dependency.id,
    )


def _node_id(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"n_{digest}"


def _process_unresolved_node_key(call: ProcessUnresolvedCall) -> str:
    return "\0".join(
        [call.process_id, call.source_service, call.target_service, call.id]
    )


def _scope_boundary_node_key(boundary_id: str) -> str:
    return f"scope-boundary\0{boundary_id}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
