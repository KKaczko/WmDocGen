from __future__ import annotations

from collections import Counter
from pathlib import Path

from wm_doc.graph_publish import GraphAsset
from wm_doc.ir import (
    AnalysisResult,
    FlowService,
    ProcessDefinition,
    ProcessDependencyEdge,
    ProcessDocumentRelationship,
    ProcessEntrypoint,
    ProcessServiceMembership,
    ProcessUnresolvedCall,
    SourceReference,
    TextValue,
)
from wm_doc.render.document_markdown import document_markdown_filename
from wm_doc.render.service_markdown import service_markdown_filename

MAX_PROCESS_ROWS = 80


def process_markdown_filename(process_id: str) -> str:
    return f"{process_id}.md"


def write_process_markdown(
    output_dir: Path, analysis: AnalysisResult, graph_assets: list[GraphAsset] | None = None
) -> list[Path]:
    if not analysis.processes:
        return []
    graph_assets = graph_assets or []
    process_dir = output_dir / "processes"
    process_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    catalog_path = process_dir / "index.md"
    catalog_path.write_text(render_process_catalog_markdown(analysis), encoding="utf-8")
    written.append(catalog_path)
    for process in sorted(analysis.processes, key=lambda item: item.process_id.casefold()):
        path = process_dir / process_markdown_filename(process.process_id)
        path.write_text(
            render_process_markdown(analysis, process, graph_assets),
            encoding="utf-8",
        )
        written.append(path)
    return written


def write_entrypoint_candidates_markdown(output_dir: Path, analysis: AnalysisResult) -> Path:
    path = output_dir / "entrypoints.md"
    path.write_text(render_entrypoint_candidates_markdown(analysis), encoding="utf-8")
    return path


def render_process_catalog_markdown(analysis: AnalysisResult) -> str:
    lines = [
        "# Process Catalog",
        "",
        (
            "Process names and descriptions are user-authored catalog facts. "
            "Counts are generated from static analysis."
        ),
        "",
        (
            "| Process | ID | Entrypoints | Resolved | Services | Edges | "
            "Unresolved Calls | Documents | Findings |"
        ),
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    entrypoints_by_process = _entrypoints_by_process(analysis)
    memberships_by_process = _memberships_by_process(analysis)
    edges_by_process = Counter(edge.process_id for edge in analysis.process_dependency_edges)
    unresolved_by_process = Counter(call.process_id for call in analysis.process_unresolved_calls)
    documents_by_process: dict[str, set[str]] = {}
    for relationship in analysis.process_document_relationships:
        documents_by_process.setdefault(relationship.process_id, set()).add(
            relationship.target_document
        )
    for process in sorted(analysis.processes, key=lambda item: item.process_id.casefold()):
        process_entrypoints = entrypoints_by_process.get(process.process_id, [])
        resolved_entrypoints = sum(1 for item in process_entrypoints if item.resolved_service)
        lines.append(
            "| "
            f"[`{process.name}`]({process_markdown_filename(process.process_id)}) | "
            f"`{process.process_id}` | "
            f"{len(process_entrypoints)} | "
            f"{resolved_entrypoints} | "
            f"{len(memberships_by_process.get(process.process_id, []))} | "
            f"{edges_by_process[process.process_id]} | "
            f"{unresolved_by_process[process.process_id]} | "
            f"{len(documents_by_process.get(process.process_id, set()))} | "
            f"{len(process.findings)} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_process_markdown(
    analysis: AnalysisResult,
    process: ProcessDefinition,
    graph_assets: list[GraphAsset] | None = None,
) -> str:
    graph_assets = graph_assets or []
    services = {
        service.identity.full_name: service
        for package in analysis.packages
        for service in package.services
    }
    entrypoints = [
        entrypoint
        for entrypoint in analysis.process_entrypoints
        if entrypoint.process_id == process.process_id
    ]
    memberships = [
        membership
        for membership in analysis.process_service_memberships
        if membership.process_id == process.process_id
    ]
    edges = [
        edge
        for edge in analysis.process_dependency_edges
        if edge.process_id == process.process_id
    ]
    unresolved = [
        call for call in analysis.process_unresolved_calls if call.process_id == process.process_id
    ]
    documents = [
        relationship
        for relationship in analysis.process_document_relationships
        if relationship.process_id == process.process_id
    ]
    document_names = {
        document.identity.full_name
        for package in analysis.packages
        for document in package.document_types
    }
    member_services = [services[item.service] for item in memberships if item.service in services]
    mapping_counts = _mapping_counts(member_services)
    java_counts = _java_counts(member_services)
    opaque_counts = _opaque_counts(member_services)
    lines = [
        f"# {process.name}",
        "",
        "## Process Identity",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Process ID | `{process.process_id}` |",
        f"| Stable ID | `{process.id}` |",
        f"| Name | `{process.name}` |",
        f"| Description status | `{process.description_status.value}` |",
        "",
        "## Business Description",
        "",
        _text_display(process.description) or "No business description was declared.",
        "",
        "## Declared Entrypoints",
        "",
        _render_declared_entrypoints(entrypoints),
        "",
        "## Entrypoint Validation",
        "",
        _render_entrypoint_validation(entrypoints, set(services)),
        "",
        "## Technical Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Services | {len(memberships)} |",
        f"| Dependency edges | {len(edges)} |",
        f"| Unresolved calls | {len(unresolved)} |",
        f"| Document relationships | {len(documents)} |",
        f"| FLOW maps | {mapping_counts['flow_maps']} |",
        f"| Mapping operations | {mapping_counts['mapping_operations']} |",
        f"| Transformer bindings | {mapping_counts['transformer_bindings']} |",
        f"| Java pipeline accesses | {java_counts['java_pipeline_accesses']} |",
        f"| Opaque services | {opaque_counts['opaque_services']} |",
        "",
        "## Process Call Graph",
        "",
        _render_process_graph_links(process, graph_assets),
        "",
        "## Services In Process",
        "",
        _render_memberships(memberships),
        "",
        "## Service Dependencies",
        "",
        _render_edges(edges),
        "",
        "## Unresolved Calls",
        "",
        _render_unresolved(unresolved),
        "",
        "## Document Types",
        "",
        _render_documents(documents, document_names),
        "",
        "## Mapping And Transformer Summary",
        "",
        _render_counter_table(mapping_counts),
        "",
        "## Java Services",
        "",
        _render_counter_table(java_counts),
        "",
        "## Opaque Services",
        "",
        _render_counter_table(opaque_counts),
        "",
        "## Findings",
        "",
        _render_findings(process),
        "",
        "## Source Evidence",
        "",
        f"- Process definition: `{process.source.path}`",
        f"- Process ID: `{process.id_source.path}`"
        + (f":{process.id_source.line}" if process.id_source.line else ""),
        f"- Process name: `{process.name_source.path}`"
        + (f":{process.name_source.line}" if process.name_source.line else ""),
        "",
        "## Analysis Limitations",
        "",
        (
            "Process membership is generated from declared entrypoints and static "
            "resolved service dependencies. It is not runtime execution evidence "
            "and does not infer external systems, branch probabilities, "
            "database behavior, scheduler behavior, or business meaning from names."
        ),
        "",
    ]
    return "\n".join(lines)


def render_entrypoint_candidates_markdown(analysis: AnalysisResult) -> str:
    lines = [
        "# Technical Entrypoint Candidates",
        "",
        "Technical root candidate; not confirmed as a business process entrypoint.",
        "",
        (
            "| Service | Type | Support | Incoming Resolved | Outgoing Resolved | "
            "Importance | Layer | Reason |"
        ),
        "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for candidate in analysis.technical_entrypoint_candidates:
        lines.append(
            "| "
            f"[`{candidate.service}`](services/{service_markdown_filename(candidate.service)}) | "
            f"`{candidate.service_type.value}` | "
            f"`{candidate.service_analysis_status.value}` | "
            f"{candidate.incoming_resolved_dependency_count} | "
            f"{candidate.outgoing_dependency_count} | "
            f"`{candidate.importance.value}` | "
            f"`{candidate.layer}` | "
            f"{candidate.reason} |"
        )
    if not analysis.technical_entrypoint_candidates:
        lines.append("| No candidates |  |  |  |  |  |  |  |")
    lines.append("")
    return "\n".join(lines)


def _entrypoints_by_process(analysis: AnalysisResult) -> dict[str, list[ProcessEntrypoint]]:
    grouped: dict[str, list[ProcessEntrypoint]] = {}
    for entrypoint in analysis.process_entrypoints:
        grouped.setdefault(entrypoint.process_id, []).append(entrypoint)
    return grouped


def _memberships_by_process(
    analysis: AnalysisResult,
) -> dict[str, list[ProcessServiceMembership]]:
    grouped: dict[str, list[ProcessServiceMembership]] = {}
    for membership in analysis.process_service_memberships:
        grouped.setdefault(membership.process_id, []).append(membership)
    return grouped


def _render_process_graph_links(
    process: ProcessDefinition, graph_assets: list[GraphAsset]
) -> str:
    dot_path = f"graphs/processes/{process.process_id}.dot"
    asset = next((item for item in graph_assets if item.dot_path == dot_path), None)
    lines = [f"- DOT graph: [`{dot_path}`](../{dot_path})"]
    if asset is None:
        return "\n".join(lines)
    svg_path = asset.rendered_paths.get("svg")
    png_path = asset.rendered_paths.get("png")
    if svg_path is not None:
        lines.append(f"- Open SVG graph: [SVG](../{svg_path})")
        lines.append("")
        lines.append(f"![Process call graph](../{svg_path})")
        if png_path is not None:
            lines.append("")
            lines.append(f"- Open PNG graph: [PNG](../{png_path})")
    elif png_path is not None:
        lines.append(f"- Open PNG graph: [PNG](../{png_path})")
        lines.append("")
        lines.append(f"![Process call graph](../{png_path})")
    return "\n".join(lines)


def _render_declared_entrypoints(entrypoints: list[ProcessEntrypoint]) -> str:
    if not entrypoints:
        return "No entrypoints were declared.\n"
    lines = [
        "| Declared Target | Source |",
        "| --- | --- |",
    ]
    for entrypoint in sorted(
        entrypoints, key=lambda item: (item.declared_target.casefold(), item.id)
    ):
        lines.append(
            "| "
            f"`{entrypoint.declared_target}` | "
            f"`{_source_display(entrypoint.source)}` |"
        )
    return "\n".join(lines) + "\n"


def _render_entrypoint_validation(
    entrypoints: list[ProcessEntrypoint], service_names: set[str]
) -> str:
    if not entrypoints:
        return "No entrypoints were declared.\n"
    lines = [
        "| Status | Declared Target | Resolved Service | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for entrypoint in sorted(
        entrypoints, key=lambda item: (item.declared_target.casefold(), item.id)
    ):
        resolved_service = _entrypoint_service_display(entrypoint, service_names)
        lines.append(
            "| "
            f"`{entrypoint.status.value}` | "
            f"`{entrypoint.declared_target}` | "
            f"{resolved_service} | "
            f"{_entrypoint_validation_evidence(entrypoint, service_names)} |"
        )
    return "\n".join(lines) + "\n"


def _render_memberships(memberships: list[ProcessServiceMembership]) -> str:
    if not memberships:
        return "No services are reachable from resolved process entrypoints.\n"
    lines = [
        "| Service | Type | Entrypoint | Depth | Reached From | Representative Path |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for membership in memberships[:MAX_PROCESS_ROWS]:
        path = ", ".join(membership.representative_path_dependency_ids)
        service_link = (
            f"[`{membership.service}`]"
            f"(../services/{service_markdown_filename(membership.service)})"
        )
        lines.append(
            "| "
            f"{service_link} | "
            f"`{membership.service_type.value}` | "
            f"{membership.entrypoint} | "
            f"{membership.minimum_depth} | "
            f"{len(membership.reached_from_entrypoint_ids)} entrypoint(s) | "
            f"`{path}` |"
        )
    if len(memberships) > MAX_PROCESS_ROWS:
        omitted = len(memberships) - MAX_PROCESS_ROWS
        lines.append(f"| ... | ... | ... | ... | ... | {omitted} omitted |")
    return "\n".join(lines) + "\n"


def _render_edges(edges: list[ProcessDependencyEdge]) -> str:
    if not edges:
        return "No resolved service dependency edges are inside this process.\n"
    lines = ["| Source | Target | Kind | Occurrences |", "| --- | --- | --- | ---: |"]
    for edge in edges[:MAX_PROCESS_ROWS]:
        lines.append(
            "| "
            f"`{edge.source_service}` | "
            f"`{edge.target_service}` | "
            f"`{edge.dependency_kind.value}` | "
            f"{edge.occurrence_count} |"
        )
    if len(edges) > MAX_PROCESS_ROWS:
        lines.append(f"| ... | ... | ... | {len(edges) - MAX_PROCESS_ROWS} omitted |")
    return "\n".join(lines) + "\n"


def _render_unresolved(calls: list[ProcessUnresolvedCall]) -> str:
    if not calls:
        return "No unresolved calls were observed from process services.\n"
    lines = ["| Caller | Target | Kind | Occurrences |", "| --- | --- | --- | ---: |"]
    for call in calls[:MAX_PROCESS_ROWS]:
        lines.append(
            "| "
            f"`{call.source_service}` | "
            f"`{call.target_service}` | "
            f"`{call.dependency_kind.value}` | "
            f"{call.occurrence_count} |"
        )
    if len(calls) > MAX_PROCESS_ROWS:
        lines.append(f"| ... | ... | ... | {len(calls) - MAX_PROCESS_ROWS} omitted |")
    return "\n".join(lines) + "\n"


def _render_documents(
    relationships: list[ProcessDocumentRelationship], document_names: set[str]
) -> str:
    if not relationships:
        return "No document relationships were derived for this process.\n"
    lines = [
        "| Document | Status | Role | Referenced By | Occurrences |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for relationship in relationships[:MAX_PROCESS_ROWS]:
        source = relationship.service or relationship.source_document or ""
        status = _document_relationship_status(relationship, document_names)
        document = _document_relationship_display(relationship, status)
        lines.append(
            "| "
            f"{document} | "
            f"`{status}` | "
            f"`{relationship.role.value}` | "
            f"`{source}` | "
            f"{relationship.occurrence_count} |"
        )
    if len(relationships) > MAX_PROCESS_ROWS:
        lines.append(
            f"| ... | ... | ... | ... | {len(relationships) - MAX_PROCESS_ROWS} omitted |"
        )
    return "\n".join(lines) + "\n"


def _entrypoint_service_display(
    entrypoint: ProcessEntrypoint, service_names: set[str]
) -> str:
    if entrypoint.resolved_service is None:
        return ""
    if entrypoint.resolved_service in service_names:
        return (
            f"[`{entrypoint.resolved_service}`]"
            f"(../services/{service_markdown_filename(entrypoint.resolved_service)})"
        )
    return f"`{entrypoint.resolved_service}`"


def _entrypoint_validation_evidence(
    entrypoint: ProcessEntrypoint, service_names: set[str]
) -> str:
    source = f"`{_source_display(entrypoint.source)}`"
    if entrypoint.resolved_service and entrypoint.resolved_service not in service_names:
        return f"{source}; resolved service page is unavailable"
    if entrypoint.status.value == "DUPLICATE":
        return f"{source}; duplicate declaration was not traversed"
    if entrypoint.status.value == "AMBIGUOUS":
        return f"{source}; canonical service identity is ambiguous"
    if entrypoint.status.value == "NOT_FOUND":
        return f"{source}; exact canonical service was not found"
    return source


def _document_relationship_status(
    relationship: ProcessDocumentRelationship, document_names: set[str]
) -> str:
    if relationship.resolved and relationship.target_document in document_names:
        return "RESOLVED"
    if relationship.resolved:
        return "RESOLVED_MISSING_DOCUMENT"
    return "UNRESOLVED"


def _document_relationship_display(
    relationship: ProcessDocumentRelationship, status: str
) -> str:
    if status == "RESOLVED":
        return (
            f"[`{relationship.target_document}`]"
            f"(../documents/{document_markdown_filename(relationship.target_document)})"
        )
    return f"`{relationship.target_document}`"


def _render_findings(process: ProcessDefinition) -> str:
    if not process.findings:
        return "No process-level findings.\n"
    lines = []
    for finding in process.findings:
        severity = f"{finding.severity.value} " if finding.severity else ""
        lines.append(
            f"- {severity}{finding.status.value} `{finding.code}` at "
            f"`{finding.source.path}`: {finding.message}"
        )
    return "\n".join(lines) + "\n"


def _render_counter_table(counts: dict[str, int]) -> str:
    if not counts:
        return "No generated summary counts for this section.\n"
    lines = ["| Metric | Count |", "| --- | ---: |"]
    for key, value in sorted(counts.items()):
        lines.append(f"| `{key}` | {value} |")
    return "\n".join(lines) + "\n"


def _mapping_counts(services: list[FlowService]) -> dict[str, int]:
    operation_counts = Counter[str]()
    transformer_services: set[str] = set()
    for service in services:
        operation_counts.update(service.metrics.mapping_operation_type_counts)
        transformer_services.update(
            binding.transformer_service for binding in service.transformer_bindings
        )
    return {
        "flow_services_with_mappings": sum(1 for service in services if service.flow_maps),
        "flow_maps": sum(service.metrics.flow_map_count for service in services),
        "mapping_operations": sum(service.metrics.mapping_operation_count for service in services),
        "MAPCOPY": operation_counts["COPY"],
        "MAPSET": operation_counts["SET"],
        "MAPDELETE": operation_counts["DELETE"],
        "transformer_bindings": sum(
            service.metrics.transformer_binding_count for service in services
        ),
        "distinct_transformer_services": len(transformer_services),
    }


def _java_counts(services: list[FlowService]) -> dict[str, int]:
    source_status_counts = Counter[str]()
    access_counts = Counter[str]()
    for service in services:
        if service.java_analysis is None:
            continue
        source_status_counts[service.java_analysis.source_set.status.value] += 1
        access_counts.update(service.java_analysis.metrics.java_pipeline_access_kind_counts)
    counts = {
        "java_services": sum(1 for service in services if service.java_analysis is not None),
        "java_pipeline_accesses": sum(
            service.java_analysis.metrics.java_pipeline_access_count
            for service in services
            if service.java_analysis is not None
        ),
        "java_static_invocations": sum(
            service.java_analysis.metrics.java_static_call_occurrence_count
            for service in services
            if service.java_analysis is not None
        ),
        "java_dynamic_invocations": sum(
            service.java_analysis.metrics.java_dynamic_call_occurrence_count
            for service in services
            if service.java_analysis is not None
        ),
    }
    counts.update({f"source_{key}": value for key, value in source_status_counts.items()})
    counts.update({f"pipeline_{key}": value for key, value in access_counts.items()})
    return counts


def _opaque_counts(services: list[FlowService]) -> dict[str, int]:
    opaque_services = [service for service in services if service.service_type.value == "OPAQUE"]
    source_types = Counter(
        service.source_service_type or "<unknown>" for service in opaque_services
    )
    description_statuses = Counter(service.description_status.value for service in opaque_services)
    counts = {"opaque_services": len(opaque_services)}
    counts.update({f"source_type_{key}": value for key, value in source_types.items()})
    counts.update({f"description_{key}": value for key, value in description_statuses.items()})
    return counts


def _text_display(text: TextValue | None) -> str | None:
    if text is None:
        return None
    if text.value:
        return text.value
    if text.marker:
        return text.marker
    return None


def _source_display(source: SourceReference) -> str:
    return source.path + (f":{source.line}" if source.line else "")
