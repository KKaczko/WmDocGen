from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from wm_doc.graph_publish import GraphAsset
from wm_doc.ir import (
    AnalysisResult,
    FlowService,
    ProcessDefinition,
    ProcessDependencyEdge,
    ProcessServiceMembership,
    UniqueDependency,
)
from wm_doc.render.document_markdown import (
    document_markdown_filename,
    render_document_markdown,
)
from wm_doc.render.service_markdown import render_service_markdown, service_markdown_filename
from wm_doc.scope_analysis import (
    ScopeBoundary,
    ScopeResult,
    ScopeSelectorType,
    ScopeServiceMembership,
)

MAX_SCOPE_ROWS = 80


def render_scope_json(scope: ScopeResult) -> str:
    payload = scope.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_scope_json(output_dir: Path, scope: ScopeResult) -> Path:
    path = output_dir / "scope.json"
    path.write_text(render_scope_json(scope), encoding="utf-8")
    return path


def render_scope_markdown(scope: ScopeResult) -> str:
    lines = [
        "# Focused Publication Scope",
        "",
        (
            "`analysis.json` describes the complete discovered snapshot. `scope.json` "
            "describes the selected publication subset. Markdown and focused graphs "
            "describe the selected publication subset."
        ),
        "",
        "## Selector",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Type | `{scope.selector.selector_type.value}` |",
        f"| Value | `{_escape_table(scope.selector.value)}` |",
        f"| Dependency depth | `{scope.selector.dependency_depth}` |",
        "",
        "## Metrics",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Roots resolved | {scope.metrics.roots_resolved} |",
        f"| Services included | {scope.metrics.services_included} |",
        f"| Included resolved dependencies | {scope.metrics.included_resolved_dependencies} |",
        f"| Boundary dependencies | {scope.metrics.boundary_dependencies} |",
        f"| Documents included | {scope.metrics.documents_included} |",
        f"| Processes published | {scope.metrics.processes_published} |",
        f"| Maximum reached depth | {scope.metrics.maximum_reached_depth} |",
        "",
        "## Roots",
        "",
        _render_root_list(scope),
        "",
        "## Boundaries",
        "",
        _render_boundaries(scope.boundaries),
        "",
        "## Findings",
        "",
        _render_findings(scope),
        "",
    ]
    return "\n".join(lines)


def write_scope_markdown(output_dir: Path, scope: ScopeResult) -> Path:
    path = output_dir / "scope.md"
    path.write_text(render_scope_markdown(scope), encoding="utf-8")
    return path


def write_scoped_service_markdown(
    output_dir: Path,
    analysis: AnalysisResult,
    scope: ScopeResult,
    services: list[FlowService],
) -> list[Path]:
    service_dir = output_dir / "services"
    service_dir.mkdir(parents=True, exist_ok=True)
    included_names = {service.identity.full_name for service in services}
    memberships = {membership.service: membership for membership in scope.service_memberships}
    boundaries_by_service = _boundaries_by_service(scope.boundaries)
    incoming = _incoming_dependencies_by_target(analysis.unique_dependencies)
    process_definitions = _scoped_process_definitions(analysis, scope)
    process_memberships_by_service = _scoped_process_memberships_by_service(analysis, scope)
    written: list[Path] = []
    for service in sorted(services, key=lambda item: item.identity.full_name.casefold()):
        path = service_dir / service_markdown_filename(service.identity.full_name)
        markdown = render_service_markdown(
            service,
            incoming.get(service.identity.full_name, []),
            process_memberships_by_service.get(service.identity.full_name, []),
            process_definitions,
        )
        markdown = _insert_scope_section(
            markdown,
            memberships[service.identity.full_name],
            boundaries_by_service.get(service.identity.full_name, []),
        )
        markdown = _replace_called_by_section(
            markdown,
            incoming.get(service.identity.full_name, []),
            included_names,
        )
        path.write_text(markdown, encoding="utf-8")
        written.append(path)
    return written


def write_scoped_document_markdown(
    output_dir: Path,
    analysis: AnalysisResult,
    scope: ScopeResult,
) -> list[Path]:
    included_documents = {membership.document for membership in scope.document_memberships}
    included_services = {membership.service for membership in scope.service_memberships}
    document_dir = output_dir / "documents"
    document_dir.mkdir(parents=True, exist_ok=True)
    selected_processes = _scoped_process_definitions(analysis, scope)
    process_relationships = [
        relationship
        for relationship in analysis.process_document_relationships
        if scope.selected_process_id is not None
        and relationship.process_id == scope.selected_process_id
    ]
    service_dependencies = [
        dependency
        for dependency in analysis.service_document_dependencies
        if dependency.service in included_services
    ]
    written: list[Path] = []
    for document in sorted(
        analysis.document_types, key=lambda item: item.identity.full_name.casefold()
    ):
        if document.identity.full_name not in included_documents:
            continue
        path = document_dir / document_markdown_filename(document.identity.full_name)
        path.write_text(
            render_document_markdown(
                document,
                analysis.document_reference_occurrences,
                analysis.document_dependencies,
                service_dependencies,
                analysis.extraction_policy,
                process_relationships,
                selected_processes,
            ),
            encoding="utf-8",
        )
        written.append(path)
    return written


def render_scoped_entrypoints_markdown(scope: ScopeResult, analysis: AnalysisResult) -> str:
    lines = [
        "# Scoped Entrypoints",
        "",
        (
            "This focused publication lists selected roots and scoped entrypoint evidence. "
            "Global technical entrypoint candidates outside the publication scope are omitted."
        ),
        "",
    ]
    if scope.selector.selector_type == ScopeSelectorType.SERVICE:
        root = scope.root_services[0] if scope.root_services else ""
        lines.extend(
            [
                "## Selected Root",
                "",
                f"- [`{root}`](services/{service_markdown_filename(root)})",
                "",
            ]
        )
    elif scope.selector.selector_type in {ScopeSelectorType.NAMESPACE, ScopeSelectorType.PACKAGE}:
        lines.extend(
            [
                "## Selected Roots",
                "",
                f"Root services: {len(scope.root_services)}",
                "",
            ]
        )
        for root in scope.root_services[:MAX_SCOPE_ROWS]:
            lines.append(f"- [`{root}`](services/{service_markdown_filename(root)})")
        if len(scope.root_services) > MAX_SCOPE_ROWS:
            lines.append(f"- ... {len(scope.root_services) - MAX_SCOPE_ROWS} roots omitted")
        lines.append("")
    else:
        lines.extend(
            [
                "## Process Entrypoints",
                "",
                _render_process_entrypoints(scope, analysis, service_prefix="services"),
            ]
        )

    scoped_candidates = [
        candidate
        for candidate in analysis.technical_entrypoint_candidates
        if candidate.service in {membership.service for membership in scope.service_memberships}
    ]
    lines.extend(
        [
            "## Scoped Technical Entrypoint Candidates",
            "",
            (
                "| Service | Type | Support | Incoming Resolved | Outgoing Resolved | "
                "Importance | Layer | Reason |"
            ),
            "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
        ]
    )
    if scoped_candidates:
        for candidate in scoped_candidates:
            service_link = (
                f"[`{candidate.service}`]"
                f"(services/{service_markdown_filename(candidate.service)})"
            )
            lines.append(
                "| "
                f"{service_link} | "
                f"`{candidate.service_type.value}` | "
                f"`{candidate.service_analysis_status.value}` | "
                f"{candidate.incoming_resolved_dependency_count} | "
                f"{candidate.outgoing_dependency_count} | "
                f"`{candidate.importance.value}` | "
                f"`{candidate.layer}` | "
                f"{candidate.reason} |"
            )
    else:
        lines.append("| No scoped candidates |  |  |  |  |  |  |  |")
    lines.append("")
    return "\n".join(lines)


def write_scoped_entrypoints_markdown(
    output_dir: Path, scope: ScopeResult, analysis: AnalysisResult
) -> Path:
    path = output_dir / "entrypoints.md"
    path.write_text(render_scoped_entrypoints_markdown(scope, analysis), encoding="utf-8")
    return path


def render_scoped_index_markdown(
    scope: ScopeResult,
    analysis: AnalysisResult,
    graph_assets: list[GraphAsset] | None = None,
) -> str:
    graph_assets = graph_assets or []
    lines = [
        "# wm-doc Focused Publication",
        "",
        (
            "`analysis.json` describes the complete discovered snapshot. `scope.json` "
            "describes the selected publication subset. Markdown and focused graphs "
            "describe the selected publication subset."
        ),
        "",
        "## Generated Inventory",
        "",
        "| Area | Count |",
        "| --- | ---: |",
        "| Full snapshot services | "
        f"{sum(len(package.services) for package in analysis.packages)} |",
        f"| Published services | {scope.metrics.services_included} |",
        f"| Published document types | {scope.metrics.documents_included} |",
        f"| Published process pages | {scope.metrics.processes_published} |",
        f"| Scope boundaries | {scope.metrics.boundary_dependencies} |",
        "",
        "## Links",
        "",
        "- [Full analysis JSON](analysis.json)",
        "- [Scope JSON](scope.json)",
        "- [Scope summary](scope.md)",
        "- [Graph catalog](graphs/index.md)",
        f"- Scope graph: {_graph_link(graph_assets, 'graphs/scope.dot')}",
        "- [Scoped entrypoints](entrypoints.md)",
        "- [Published services](services/)",
    ]
    if scope.metrics.documents_included:
        lines.append("- [Published document types](documents/)")
    if scope.selected_process_id is not None:
        lines.append("- [Published process page](processes/index.md)")
    lines.extend(
        [
            "",
            "## Disclosure Policy",
            "",
            f"- Free text mode: {analysis.extraction_policy.free_text_mode}",
            f"- Literal mode: {analysis.extraction_policy.literal_mode}",
            "- Secret guard: enabled"
            if analysis.extraction_policy.secret_guard.enabled
            else "- Secret guard: disabled",
            f"- Secret guard strategy: {analysis.extraction_policy.secret_guard.strategy_version}",
            "",
            "## Limitations",
            "",
            (
                "This is a focused publication scope. The underlying technical analysis "
                "still parsed and resolved the complete snapshot before publication was scoped."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_scoped_index_markdown(
    output_dir: Path,
    scope: ScopeResult,
    analysis: AnalysisResult,
    graph_assets: list[GraphAsset] | None = None,
) -> Path:
    path = output_dir / "index.md"
    path.write_text(render_scoped_index_markdown(scope, analysis, graph_assets), encoding="utf-8")
    return path


def render_scoped_process_catalog_markdown(scope: ScopeResult) -> str:
    lines = [
        "# Scoped Process Catalog",
        "",
        "Only the selected process publication is included in this focused output.",
        "",
        (
            "| Process | Full Members | Published Members | Full Edges | "
            "Published Edges | Boundaries |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    if not scope.process_projections:
        lines.append("| No selected process |  |  |  |  |  |")
    for projection in scope.process_projections:
        lines.append(
            "| "
            f"[`{projection.process_name}`]({projection.process_id}.md) | "
            f"{projection.full_member_count} | "
            f"{projection.published_member_count} | "
            f"{projection.full_edge_count} | "
            f"{projection.published_edge_count} | "
            f"{projection.boundary_dependency_count} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_scoped_process_markdown(
    scope: ScopeResult,
    analysis: AnalysisResult,
    process: ProcessDefinition,
    graph_assets: list[GraphAsset] | None = None,
) -> str:
    graph_assets = graph_assets or []
    included_services = {membership.service for membership in scope.service_memberships}
    projection = scope.process_projections[0] if scope.process_projections else None
    published_edges = [
        edge
        for edge in analysis.process_dependency_edges
        if edge.process_id == process.process_id
        and edge.source_service in included_services
        and edge.target_service in included_services
    ]
    published_boundaries = [
        boundary for boundary in scope.boundaries if boundary.source_service in included_services
    ]
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
        "## Publication Projection",
        "",
        (
            "Full-process facts come from the complete static process analysis. "
            "Published facts are projected onto the selected focused publication scope."
        ),
        "",
        "| Metric | Count |",
        "| --- | ---: |",
    ]
    if projection is not None:
        lines.extend(
            [
                f"| Published dependency depth | `{scope.selector.dependency_depth}` |",
                f"| Full discovered process members | {projection.full_member_count} |",
                f"| Published process members | {projection.published_member_count} |",
                f"| Full process dependency edges | {projection.full_edge_count} |",
                f"| Published process dependency edges | {projection.published_edge_count} |",
                f"| Boundary dependencies | {projection.boundary_dependency_count} |",
            ]
        )
    lines.extend(
        [
            "",
            "## Declared Entrypoints",
            "",
            _render_process_entrypoints(scope, analysis),
            "",
            "## Process Call Graph",
            "",
            _render_process_graph_links(process.process_id, graph_assets),
            "",
            "## Published Services",
            "",
            _render_scope_service_table(scope),
            "",
            "## Published Dependencies",
            "",
            _render_published_process_edges(published_edges),
            "",
            "## Boundaries",
            "",
            _render_boundaries(published_boundaries),
            "",
            "## Documents",
            "",
            _render_scope_documents(scope),
            "",
            "## Findings",
            "",
            _render_process_findings(process),
            "",
        ]
    )
    return "\n".join(lines)


def write_scoped_process_markdown(
    output_dir: Path,
    scope: ScopeResult,
    analysis: AnalysisResult,
    graph_assets: list[GraphAsset] | None = None,
) -> list[Path]:
    if scope.selected_process_id is None:
        return []
    process = next(
        (item for item in analysis.processes if item.process_id == scope.selected_process_id),
        None,
    )
    if process is None:
        return []
    process_dir = output_dir / "processes"
    process_dir.mkdir(parents=True, exist_ok=True)
    catalog_path = process_dir / "index.md"
    catalog_path.write_text(render_scoped_process_catalog_markdown(scope), encoding="utf-8")
    page_path = process_dir / f"{process.process_id}.md"
    page_path.write_text(
        render_scoped_process_markdown(scope, analysis, process, graph_assets),
        encoding="utf-8",
    )
    return [catalog_path, page_path]


def _insert_scope_section(
    markdown: str,
    membership: ScopeServiceMembership,
    boundaries: list[ScopeBoundary],
) -> str:
    root_samples = ", ".join(f"`{root}`" for root in membership.reaching_root_samples)
    path_samples = "; ".join(
        f"{sample.root_service}: {' -> '.join(sample.dependency_ids) or '<root>'}"
        for sample in membership.representative_path_samples
    )
    reasons = ", ".join(reason.value for reason in membership.inclusion_reasons)
    section = "\n".join(
        [
            "## Scope",
            "",
            "| Field | Value |",
            "| --- | --- |",
            f"| Is root | {membership.is_root} |",
            f"| Minimum depth | {membership.minimum_depth} |",
            f"| Inclusion reasons | `{reasons}` |",
            f"| Reaching root count | {membership.reaching_root_count} |",
            f"| Reaching root samples | {root_samples or ''} |",
            f"| Reaching root samples omitted | {membership.reaching_root_samples_omitted} |",
            f"| Representative path samples | `{_escape_table(path_samples)}` |",
            "| Representative path samples omitted | "
            f"{membership.representative_path_samples_omitted} |",
            "",
            "## Scope Boundaries",
            "",
            _render_boundaries(boundaries),
            "",
        ]
    )
    return markdown.replace("## Input Signature", f"{section}## Input Signature", 1)


def _replace_called_by_section(
    markdown: str,
    incoming_dependencies: list[UniqueDependency],
    included_names: set[str],
) -> str:
    start_marker = "## Called By"
    end_marker = "\n## Processes"
    start = markdown.find(start_marker)
    end = markdown.find(end_marker, start)
    if start == -1 or end == -1:
        return markdown
    called_by = _render_scoped_called_by(incoming_dependencies, included_names)
    replacement = f"{start_marker}\n\n{called_by}"
    return markdown[:start] + replacement + markdown[end:]


def _render_scoped_called_by(
    dependencies: list[UniqueDependency], included_names: set[str]
) -> str:
    if not dependencies:
        return "No incoming static service calls target this service.\n"
    lines = [
        "| Occurrences | Scope | Resolved | Source | Kind | Source sample |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    outside_count = 0
    for dependency in sorted(dependencies, key=_incoming_dependency_key):
        inside = dependency.source_service in included_names
        if not inside:
            outside_count += 1
        source = (
            f"[`{dependency.source_service}`]"
            f"(../services/{service_markdown_filename(dependency.source_service)})"
            if inside
            else f"`{dependency.source_service}`"
        )
        sample = dependency.source_samples[0] if dependency.source_samples else None
        sample_text = (
            sample.path + (f":{sample.line}" if sample and sample.line else "")
            if sample
            else ""
        )
        lines.append(
            "| "
            f"{dependency.occurrence_count} | "
            f"`{'inside publication scope' if inside else 'outside publication scope'}` | "
            f"{dependency.resolved} | "
            f"{source} | "
            f"`{dependency.dependency_kind.value}` | "
            f"`{sample_text}` |"
        )
    if outside_count:
        lines.append(
            f"|  | `outside publication scope count` |  | `{outside_count}` |  |  |"
        )
    return "\n".join(lines) + "\n"


def _render_process_entrypoints(
    scope: ScopeResult,
    analysis: AnalysisResult,
    *,
    service_prefix: str = "../services",
) -> str:
    if scope.selected_process_id is None:
        return "No process selector is active.\n"
    included = {membership.service for membership in scope.service_memberships}
    entrypoints = [
        entrypoint
        for entrypoint in analysis.process_entrypoints
        if entrypoint.process_id == scope.selected_process_id
    ]
    if not entrypoints:
        return "No entrypoints were declared for the selected process.\n"
    lines = ["| Status | Declared Target | Resolved Service |", "| --- | --- | --- |"]
    for entrypoint in sorted(
        entrypoints, key=lambda item: (item.declared_target.casefold(), item.id)
    ):
        if entrypoint.resolved_service and entrypoint.resolved_service in included:
            resolved = (
                f"[`{entrypoint.resolved_service}`]"
                f"({service_prefix}/{service_markdown_filename(entrypoint.resolved_service)})"
            )
        elif entrypoint.resolved_service:
            resolved = f"`{entrypoint.resolved_service}`"
        else:
            resolved = ""
        lines.append(
            "| "
            f"`{entrypoint.status.value}` | "
            f"`{entrypoint.declared_target}` | "
            f"{resolved} |"
        )
    return "\n".join(lines) + "\n"


def _render_scope_service_table(scope: ScopeResult) -> str:
    if not scope.service_memberships:
        return "No services are included in this focused publication scope.\n"
    lines = ["| Service | Root | Depth | Reasons |", "| --- | --- | ---: | --- |"]
    for membership in scope.service_memberships[:MAX_SCOPE_ROWS]:
        service_link = (
            f"[`{membership.service}`]"
            f"(../services/{service_markdown_filename(membership.service)})"
        )
        lines.append(
            "| "
            f"{service_link} | "
            f"{membership.is_root} | "
            f"{membership.minimum_depth} | "
            f"`{', '.join(reason.value for reason in membership.inclusion_reasons)}` |"
        )
    if len(scope.service_memberships) > MAX_SCOPE_ROWS:
        omitted = len(scope.service_memberships) - MAX_SCOPE_ROWS
        lines.append(f"| ... | ... | ... | {omitted} omitted |")
    return "\n".join(lines) + "\n"


def _render_published_process_edges(edges: list[ProcessDependencyEdge]) -> str:
    if not edges:
        return "No process dependency edges are published inside this scope.\n"
    lines = ["| Source | Target | Kind | Occurrences |", "| --- | --- | --- | ---: |"]
    for edge in sorted(
        edges,
        key=lambda item: (
            item.source_service.casefold(),
            item.target_service.casefold(),
            item.dependency_kind.value,
            item.id,
        ),
    )[:MAX_SCOPE_ROWS]:
        lines.append(
            "| "
            f"`{edge.source_service}` | "
            f"`{edge.target_service}` | "
            f"`{edge.dependency_kind.value}` | "
            f"{edge.occurrence_count} |"
        )
    return "\n".join(lines) + "\n"


def _render_scope_documents(scope: ScopeResult) -> str:
    if not scope.document_memberships:
        return "No document types are included in this focused publication scope.\n"
    lines = ["| Document | Direct | Depth | Reasons |", "| --- | --- | ---: | --- |"]
    for membership in scope.document_memberships[:MAX_SCOPE_ROWS]:
        document_link = (
            f"[`{membership.document}`]"
            f"(../documents/{document_markdown_filename(membership.document)})"
        )
        lines.append(
            "| "
            f"{document_link} | "
            f"{membership.direct} | "
            f"{membership.minimum_document_depth} | "
            f"`{', '.join(reason.value for reason in membership.inclusion_reasons)}` |"
        )
    if len(scope.document_memberships) > MAX_SCOPE_ROWS:
        omitted = len(scope.document_memberships) - MAX_SCOPE_ROWS
        lines.append(f"| ... | ... | ... | {omitted} omitted |")
    return "\n".join(lines) + "\n"


def _render_root_list(scope: ScopeResult) -> str:
    if not scope.root_services:
        return "No root services were resolved.\n"
    lines = []
    for root in scope.root_services[:MAX_SCOPE_ROWS]:
        lines.append(f"- [`{root}`](services/{service_markdown_filename(root)})")
    if len(scope.root_services) > MAX_SCOPE_ROWS:
        lines.append(f"- ... {len(scope.root_services) - MAX_SCOPE_ROWS} roots omitted")
    return "\n".join(lines) + "\n"


def _render_boundaries(boundaries: list[ScopeBoundary]) -> str:
    if not boundaries:
        return "No scope boundaries were recorded.\n"
    lines = [
        "| Status | Source | Target | Kind | Occurrences |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for boundary in sorted(
        boundaries,
        key=lambda item: (
            item.status.value,
            item.source_service.casefold(),
            item.target.casefold(),
            item.id,
        ),
    )[:MAX_SCOPE_ROWS]:
        lines.append(
            "| "
            f"`{boundary.status.value}` | "
            f"`{boundary.source_service}` | "
            f"`{_escape_table(boundary.target)}` | "
            f"`{boundary.dependency_or_call_kind}` | "
            f"{boundary.occurrence_count} |"
        )
    if len(boundaries) > MAX_SCOPE_ROWS:
        lines.append(f"| ... | ... | ... | ... | {len(boundaries) - MAX_SCOPE_ROWS} omitted |")
    return "\n".join(lines) + "\n"


def _render_findings(scope: ScopeResult) -> str:
    if not scope.findings:
        return "No scope-level findings.\n"
    lines = []
    for finding in scope.findings:
        severity = f"{finding.severity.value} " if finding.severity else ""
        lines.append(
            f"- {severity}{finding.status.value} `{finding.code}` at "
            f"`{finding.source.path}`: {finding.message}"
        )
    return "\n".join(lines) + "\n"


def _render_process_findings(process: ProcessDefinition) -> str:
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


def _render_process_graph_links(process_id: str, graph_assets: list[GraphAsset]) -> str:
    dot_path = f"graphs/processes/{process_id}.dot"
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


def _graph_link(graph_assets: list[GraphAsset], dot_path: str) -> str:
    asset = next((item for item in graph_assets if item.dot_path == dot_path), None)
    if asset is None:
        return f"[DOT]({dot_path})"
    if "svg" in asset.rendered_paths:
        return f"[SVG]({asset.rendered_paths['svg']}) ([DOT]({asset.dot_path}))"
    if "png" in asset.rendered_paths:
        return f"[PNG]({asset.rendered_paths['png']}) ([DOT]({asset.dot_path}))"
    return f"[DOT]({asset.dot_path})"


def _incoming_dependencies_by_target(
    dependencies: list[UniqueDependency],
) -> dict[str, list[UniqueDependency]]:
    incoming: dict[str, list[UniqueDependency]] = defaultdict(list)
    for dependency in dependencies:
        if dependency.resolved:
            incoming[dependency.target_service].append(dependency)
    return {
        target: sorted(items, key=_incoming_dependency_key)
        for target, items in incoming.items()
    }


def _boundaries_by_service(
    boundaries: list[ScopeBoundary],
) -> dict[str, list[ScopeBoundary]]:
    grouped: dict[str, list[ScopeBoundary]] = defaultdict(list)
    for boundary in boundaries:
        grouped[boundary.source_service].append(boundary)
    return {
        service: sorted(
            items,
            key=lambda item: (item.status.value, item.target.casefold(), item.id),
        )
        for service, items in grouped.items()
    }


def _scoped_process_definitions(
    analysis: AnalysisResult, scope: ScopeResult
) -> dict[str, ProcessDefinition]:
    if scope.selected_process_id is None:
        return {}
    return {
        process.process_id: process
        for process in analysis.processes
        if process.process_id == scope.selected_process_id
    }


def _scoped_process_memberships_by_service(
    analysis: AnalysisResult, scope: ScopeResult
) -> dict[str, list[ProcessServiceMembership]]:
    if scope.selected_process_id is None:
        return {}
    included = {membership.service for membership in scope.service_memberships}
    grouped: dict[str, list[ProcessServiceMembership]] = defaultdict(list)
    for membership in analysis.process_service_memberships:
        if membership.process_id != scope.selected_process_id:
            continue
        if membership.service in included:
            grouped[membership.service].append(membership)
    return {
        service: sorted(items, key=lambda item: (item.process_id.casefold(), item.id))
        for service, items in grouped.items()
    }


def _incoming_dependency_key(dependency: UniqueDependency) -> tuple[str, str, str]:
    return (
        dependency.source_service.casefold(),
        dependency.dependency_kind.value,
        dependency.id,
    )


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
