from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer

from wm_doc.analysis import analyze_path
from wm_doc.config import load_config
from wm_doc.discovery import scan_path
from wm_doc.graph_publish import (
    GRAPH_RENDER_TIMEOUT_SECONDS,
    GraphRenderFormat,
    GraphRenderMode,
    GraphRenderResult,
    GraphvizRunner,
    _safe_diagnostic,
    build_graph_assets,
    graph_render_failures,
    render_graphs,
    rendered_count,
    run_subprocess,
)
from wm_doc.ir import AnalysisResult
from wm_doc.render.analysis_json import render_analysis_json
from wm_doc.render.document_markdown import write_document_markdown
from wm_doc.render.dot import (
    write_dependency_dot,
    write_document_dot,
    write_process_dots,
    write_scope_document_dot,
    write_scope_dot,
    write_scoped_process_dot,
)
from wm_doc.render.graph_markdown import write_graph_index
from wm_doc.render.index_markdown import write_documentation_index
from wm_doc.render.json import render_inventory_json
from wm_doc.render.markdown import render_inventory_markdown
from wm_doc.render.process_markdown import (
    write_entrypoint_candidates_markdown,
    write_process_markdown,
)
from wm_doc.render.scope_markdown import (
    write_scope_json,
    write_scope_markdown,
    write_scoped_document_markdown,
    write_scoped_entrypoints_markdown,
    write_scoped_index_markdown,
    write_scoped_process_markdown,
    write_scoped_service_markdown,
)
from wm_doc.render.service_markdown import write_service_markdown
from wm_doc.scope_analysis import (
    ScopeRequest,
    ScopeResult,
    ScopeSelectorType,
    build_focused_scope,
    services_for_scope,
    validate_scope_request,
)

app = typer.Typer(
    help="Offline deterministic static inventory for webMethods Integration Server packages."
)

GRAPHVIZ_RUNNER: GraphvizRunner = run_subprocess
MANAGED_ROOT_FILES = ("analysis.json", "index.md", "entrypoints.md", "scope.json", "scope.md")
MANAGED_ROOT_DIRS = ("services", "documents", "processes", "graphs")


@app.callback()
def main() -> None:
    """Offline deterministic static inventory for webMethods packages."""


@app.command()
def scan(
    packages_path: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True, readable=True)
    ],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Directory for inventory outputs.")
    ],
) -> None:
    """Discover packages and artifact candidates without executing analyzed code."""
    inventory = scan_path(packages_path)
    output.mkdir(parents=True, exist_ok=True)
    (output / "inventory.json").write_text(render_inventory_json(inventory), encoding="utf-8")
    (output / "fixture-inventory.md").write_text(
        render_inventory_markdown(inventory), encoding="utf-8"
    )
    typer.echo(
        f"Scanned {len(inventory.packages)} package(s); wrote {output / 'inventory.json'} "
        f"and {output / 'fixture-inventory.md'}."
    )


@app.command()
def analyze(
    packages_path: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, dir_okay=True, readable=True)
    ],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Directory for analysis outputs.")
    ],
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", exists=True, file_okay=True, dir_okay=False, readable=True),
    ] = None,
    processes_file: Annotated[
        Path | None,
        typer.Option(
            "--processes-file",
            help="Optional processes.yml catalog for user-authored process entrypoints.",
        ),
    ] = None,
    render_graphs_mode: Annotated[
        GraphRenderMode,
        typer.Option(
            "--render-graphs",
            help="Render generated DOT graphs with Graphviz.",
        ),
    ] = GraphRenderMode.NONE,
    graphviz_dot: Annotated[
        Path | None,
        typer.Option(
            "--graphviz-dot",
            help="Optional path to the Graphviz dot executable.",
        ),
    ] = None,
    target_service: Annotated[
        list[str] | None,
        typer.Option(
            "--target-service",
            help="Publish a focused scope rooted at one exact canonical service name.",
        ),
    ] = None,
    target_namespace: Annotated[
        list[str] | None,
        typer.Option(
            "--target-namespace",
            help="Publish a focused scope rooted at a namespace prefix and descendants.",
        ),
    ] = None,
    target_package: Annotated[
        list[str] | None,
        typer.Option(
            "--target-package",
            help="Publish a focused scope rooted at one exact package identity.",
        ),
    ] = None,
    target_process: Annotated[
        list[str] | None,
        typer.Option(
            "--target-process",
            help="Publish a focused scope rooted at one exact processes.yml process id.",
        ),
    ] = None,
    dependency_depth: Annotated[
        str,
        typer.Option(
            "--dependency-depth",
            help="Focused publication dependency depth: 0, 1, N, or all.",
        ),
    ] = "all",
) -> None:
    """Analyze supported services and emit deterministic technical outputs."""
    try:
        scope_request = _scope_request_from_cli(
            target_service=target_service,
            target_namespace=target_namespace,
            target_package=target_package,
            target_process=target_process,
            dependency_depth=dependency_depth,
        )
    except ScopeCliError as exc:
        typer.echo(f"{exc.code}: {exc.safe_message}", err=True)
        raise typer.Exit(code=2) from exc
    app_config = load_config(config)
    analysis = analyze_path(
        packages_path,
        app_config,
        processes_file,
        processes_file_explicit=processes_file is not None,
    )
    if scope_request is not None:
        process_catalog_available = _process_catalog_available(packages_path, processes_file)
        scope_output = build_focused_scope(
            analysis,
            scope_request,
            process_catalog_available=process_catalog_available,
        )
        if not scope_output.should_publish or scope_output.scope is None:
            code_suffix = f" [{scope_output.code}]" if scope_output.code is not None else ""
            typer.echo(
                f"Focused publication scope failed{code_suffix}:\n"
                f"{scope_output.message or 'scope could not be resolved'}",
                err=True,
            )
            raise typer.Exit(code=scope_output.exit_code or 1)
        graph_failures = _write_scoped_outputs(
            output,
            analysis,
            scope_output.scope,
            render_graphs_mode,
            graphviz_dot,
        )
        if graph_failures:
            _echo_graph_failures(graph_failures)
            raise typer.Exit(code=1)
        if scope_output.exit_code:
            typer.echo(
                "Focused publication completed with scope findings that require attention.",
                err=True,
            )
            raise typer.Exit(code=scope_output.exit_code)
        return
    output.mkdir(parents=True, exist_ok=True)
    try:
        _clean_generated_output(output)
    except OutputCleanupError as exc:
        typer.echo(f"Output cleanup failed: {exc.safe_message}", err=True)
        raise typer.Exit(code=1) from exc
    (output / "analysis.json").write_text(render_analysis_json(analysis), encoding="utf-8")
    services = [service for package in analysis.packages for service in package.services]
    documents = [document for package in analysis.packages for document in package.document_types]
    service_paths = write_service_markdown(
        output,
        services,
        analysis.process_service_memberships,
        analysis.processes,
    )
    document_paths = write_document_markdown(
        output,
        documents,
        analysis.document_reference_occurrences,
        analysis.document_dependencies,
        analysis.service_document_dependencies,
        analysis.extraction_policy,
        analysis.process_document_relationships,
        analysis.processes,
    )
    entrypoint_path = write_entrypoint_candidates_markdown(output, analysis)
    dot_path = write_dependency_dot(output, analysis)
    document_dot_path = write_document_dot(output, analysis)
    process_dot_paths = write_process_dots(output, analysis)
    dot_paths = [dot_path, document_dot_path, *process_dot_paths]
    graph_assets = build_graph_assets(output, dot_paths)
    graph_results = render_graphs(
        output,
        graph_assets,
        render_graphs_mode,
        graphviz_dot=graphviz_dot,
        runner=GRAPHVIZ_RUNNER,
        timeout=GRAPH_RENDER_TIMEOUT_SECONDS,
    )
    graph_failures = graph_render_failures(graph_results)
    graph_index_path = write_graph_index(output, graph_assets)
    index_path = write_documentation_index(output, analysis, graph_assets)
    process_paths = write_process_markdown(output, analysis, graph_assets)
    flow_count = sum(1 for service in services if service.service_type.value == "FLOW")
    java_count = sum(1 for service in services if service.service_type.value == "JAVA")
    opaque_count = sum(1 for service in services if service.service_type.value == "OPAQUE")
    metrics = analysis.metrics
    typer.echo(
        "Analyzed services:\n"
        f"- FLOW: {flow_count}\n"
        f"- Java: {java_count}\n"
        f"- Opaque: {opaque_count}\n"
        f"- total: {len(services)}\n"
        "Analysis support status:\n"
        f"- full: {metrics.service_analysis_status_counts.get('FULL', 0)}\n"
        f"- partial: {metrics.service_analysis_status_counts.get('PARTIAL', 0)}\n"
        f"- opaque: {metrics.service_analysis_status_counts.get('OPAQUE', 0)}\n"
        "Opaque service descriptions:\n"
        f"- with source descriptions: {metrics.opaque_service_with_description_count}\n"
        f"- without source descriptions: {metrics.opaque_service_without_description_count}\n"
        "Service call occurrences:\n"
        f"- FLOW: {metrics.flow_call_occurrence_count}\n"
        f"- Java static: {metrics.java_static_call_occurrence_count}\n"
        f"- Java dynamic/partial: {metrics.java_dynamic_call_occurrence_count}\n"
        f"- total promoted calls: {metrics.total_call_occurrence_count}\n"
        "Resolved call targets by type:\n"
        f"- Opaque: {metrics.resolved_call_occurrence_target_type_counts.get('OPAQUE', 0)}\n"
        "Unique service dependencies:\n"
        f"- FLOW-derived: {metrics.flow_unique_dependency_count}\n"
        f"- Java-derived: {metrics.java_unique_dependency_count}\n"
        f"- total: {metrics.total_unique_dependency_count}\n"
        "Resolved unique dependency targets by type:\n"
        f"- Opaque: {metrics.resolved_unique_dependency_target_type_counts.get('OPAQUE', 0)}\n"
        "Processes:\n"
        f"- definitions: {metrics.process_definition_count}\n"
        f"- resolved entrypoints: {metrics.resolved_entrypoint_count}\n"
        f"- unresolved entrypoints: {metrics.unresolved_entrypoint_count}\n"
        f"- technical entrypoint candidates: {metrics.technical_entrypoint_candidate_count}\n"
        f"- service memberships: {metrics.process_service_membership_count}\n"
        f"- dependency edges: {metrics.process_dependency_edge_count}\n"
        f"- unresolved process calls: {metrics.process_unresolved_call_count}\n"
        f"- Processes with findings: {metrics.processes_with_findings_count}\n"
        "Wrote analysis.json, "
        f"{index_path.name}, "
        f"{len(service_paths)} service markdown file(s), "
        f"{len(document_paths)} document markdown file(s), "
        f"{len(process_paths)} process markdown file(s), "
        f"{entrypoint_path.name}, "
        f"{dot_path.parent.name}/{dot_path.name}, "
        f"{document_dot_path.parent.name}/{document_dot_path.name}, and "
        f"{len(process_dot_paths)} process DOT file(s).\n"
        "Graph publishing:\n"
        f"- DOT graphs generated: {len(dot_paths)}\n"
        f"- SVG graphs rendered: {rendered_count(graph_assets, GraphRenderFormat.SVG)}\n"
        f"- PNG graphs rendered: {rendered_count(graph_assets, GraphRenderFormat.PNG)}\n"
        f"- Graph render failures: {len(graph_failures)}\n"
        f"- Graph index generated: {'yes' if graph_index_path.exists() else 'no'}"
    )
    if graph_failures:
        _echo_graph_failures(graph_failures)
        raise typer.Exit(code=1)


def _write_scoped_outputs(
    output: Path,
    analysis: AnalysisResult,
    scope: ScopeResult,
    render_graphs_mode: GraphRenderMode,
    graphviz_dot: Path | None,
) -> list[GraphRenderResult]:
    output.mkdir(parents=True, exist_ok=True)
    try:
        _clean_generated_output(output)
    except OutputCleanupError as exc:
        typer.echo(f"Output cleanup failed: {exc.safe_message}", err=True)
        raise typer.Exit(code=1) from exc

    (output / "analysis.json").write_text(render_analysis_json(analysis), encoding="utf-8")
    write_scope_json(output, scope)
    write_scope_markdown(output, scope)
    services = services_for_scope(analysis, scope)
    service_paths = write_scoped_service_markdown(output, analysis, scope, services)
    document_paths = write_scoped_document_markdown(output, analysis, scope)
    entrypoint_path = write_scoped_entrypoints_markdown(output, scope, analysis)
    dot_paths = [write_scope_dot(output, scope)]
    document_dot_path = write_scope_document_dot(output, scope)
    if document_dot_path is not None:
        dot_paths.append(document_dot_path)
    process_dot_path = write_scoped_process_dot(output, scope)
    if process_dot_path is not None:
        dot_paths.append(process_dot_path)
    graph_assets = build_graph_assets(output, dot_paths)
    graph_results = render_graphs(
        output,
        graph_assets,
        render_graphs_mode,
        graphviz_dot=graphviz_dot,
        runner=GRAPHVIZ_RUNNER,
        timeout=GRAPH_RENDER_TIMEOUT_SECONDS,
    )
    graph_failures = graph_render_failures(graph_results)
    graph_index_path = write_graph_index(output, graph_assets)
    index_path = write_scoped_index_markdown(output, scope, analysis, graph_assets)
    process_paths = write_scoped_process_markdown(output, scope, analysis, graph_assets)
    metrics = scope.metrics
    typer.echo(
        "Full snapshot technical metrics:\n"
        f"- services: {sum(len(package.services) for package in analysis.packages)}\n"
        f"- unique service dependencies: {analysis.metrics.total_unique_dependency_count}\n"
        f"- document types: {analysis.metrics.document_type_count}\n"
        f"- technical entrypoint candidates: "
        f"{analysis.metrics.technical_entrypoint_candidate_count}\n"
        "Focused publication metrics:\n"
        f"- selector type: {metrics.selector_type.value}\n"
        f"- selector value: {_safe_cli_value(metrics.selector_value)}\n"
        f"- dependency depth: {metrics.dependency_depth}\n"
        f"- roots resolved: {metrics.roots_resolved}\n"
        f"- services included: {metrics.services_included}\n"
        f"- root services included: {metrics.root_services_included}\n"
        f"- included resolved dependencies: {metrics.included_resolved_dependencies}\n"
        f"- boundary dependencies: {metrics.boundary_dependencies}\n"
        f"- depth-limit boundaries: "
        f"{metrics.boundary_counts_by_status.get('DEPTH_LIMIT', 0)}\n"
        f"- unresolved static boundaries: "
        f"{metrics.boundary_counts_by_status.get('UNRESOLVED', 0)}\n"
        f"- dynamic boundaries: {metrics.boundary_counts_by_status.get('DYNAMIC', 0)}\n"
        f"- external built-in boundaries: "
        f"{metrics.boundary_counts_by_status.get('EXTERNAL_BUILTIN', 0)}\n"
        f"- documents included: {metrics.documents_included}\n"
        f"- direct documents included: {metrics.direct_documents_included}\n"
        f"- transitive documents included: {metrics.transitive_documents_included}\n"
        f"- processes published: {metrics.processes_published}\n"
        f"- maximum reached depth: {metrics.maximum_reached_depth}\n"
        "Wrote full analysis.json plus focused publication files: "
        f"scope.json, scope.md, {index_path.name}, "
        f"{len(service_paths)} service markdown file(s), "
        f"{len(document_paths)} document markdown file(s), "
        f"{len(process_paths)} process markdown file(s), "
        f"{entrypoint_path.name}.\n"
        "Graph publishing:\n"
        f"- DOT graphs generated: {len(dot_paths)}\n"
        f"- SVG graphs rendered: {rendered_count(graph_assets, GraphRenderFormat.SVG)}\n"
        f"- PNG graphs rendered: {rendered_count(graph_assets, GraphRenderFormat.PNG)}\n"
        f"- Graph render failures: {len(graph_failures)}\n"
        f"- Graph index generated: {'yes' if graph_index_path.exists() else 'no'}"
    )
    return graph_failures


def _echo_graph_failures(graph_failures: list[GraphRenderResult]) -> None:
    typer.echo("Graph rendering failed:", err=True)
    for failure in graph_failures:
        typer.echo(
            "- "
            f"{failure.dot_path} {failure.requested_format.value}: "
            f"{failure.failure_reason or 'render failed'}",
            err=True,
        )


def _scope_request_from_cli(
    *,
    target_service: list[str] | None,
    target_namespace: list[str] | None,
    target_package: list[str] | None,
    target_process: list[str] | None,
    dependency_depth: str,
) -> ScopeRequest | None:
    selectors: list[tuple[ScopeSelectorType, str]] = []
    for selector_type, values, option_name in (
        (ScopeSelectorType.SERVICE, target_service, "--target-service"),
        (ScopeSelectorType.NAMESPACE, target_namespace, "--target-namespace"),
        (ScopeSelectorType.PACKAGE, target_package, "--target-package"),
        (ScopeSelectorType.PROCESS, target_process, "--target-process"),
    ):
        values = values or []
        if len(values) > 1:
            raise ScopeCliError(
                "SCOPE_SELECTOR_CONFLICT",
                f"{option_name} may be provided at most once in M8a v1.",
            )
        if values:
            selectors.append((selector_type, values[0].strip()))

    depth = _parse_dependency_depth(dependency_depth)
    if len(selectors) > 1:
        raise ScopeCliError(
            "SCOPE_SELECTOR_CONFLICT",
            "M8a v1 accepts exactly one focused publication selector per run.",
        )
    if not selectors:
        if depth is not None:
            raise ScopeCliError(
                "SCOPE_SELECTOR_CONFLICT",
                "--dependency-depth requires a focused publication selector.",
            )
        return None

    selector_type, selector_value = selectors[0]
    request = ScopeRequest(selector_type, selector_value, depth)
    malformed = validate_scope_request(request)
    if malformed is not None:
        raise ScopeCliError(malformed.code, malformed.message)
    return request


def _parse_dependency_depth(value: str) -> int | None:
    normalized = value.strip().casefold()
    if normalized == "all":
        return None
    try:
        parsed = int(normalized, 10)
    except ValueError as exc:
        raise ScopeCliError(
            "SCOPE_TARGET_MALFORMED",
            "--dependency-depth must be 0, a positive integer, or all.",
        ) from exc
    if parsed < 0:
        raise ScopeCliError(
            "SCOPE_TARGET_MALFORMED",
            "--dependency-depth must be 0, a positive integer, or all.",
        )
    return parsed


def _process_catalog_available(packages_path: Path, processes_file: Path | None) -> bool:
    if processes_file is not None:
        return processes_file.exists()
    return (packages_path / "processes.yml").exists()


def _safe_cli_value(value: str) -> str:
    cleaned = "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in value)
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > 120:
        return cleaned[:120] + "..."
    return cleaned


class ScopeCliError(Exception):
    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(f"{code}: {safe_message}")
        self.code = code
        self.safe_message = safe_message


def _clean_generated_output(output: Path) -> None:
    for filename in MANAGED_ROOT_FILES:
        _remove_managed_path(output, Path(filename))
    for directory in MANAGED_ROOT_DIRS:
        _remove_managed_path(output, Path(directory))


def _remove_managed_path(output: Path, relative_path: Path) -> None:
    target = output / relative_path
    if not target.exists() and not target.is_symlink():
        return
    _validate_managed_path(output, target, relative_path)
    try:
        if target.is_symlink():
            target.unlink()
        elif _is_junction(target):
            target.rmdir()
        elif target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    except OSError as exc:
        raise OutputCleanupError(
            "OUTPUT_CLEANUP_FAILED",
            f"Could not remove managed generated output path `{relative_path.as_posix()}`.",
            _safe_diagnostic(str(exc), output),
        ) from exc


def _validate_managed_path(output: Path, target: Path, relative_path: Path) -> None:
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise OutputCleanupError(
            "OUTPUT_PATH_UNSAFE",
            f"Managed generated output path `{relative_path.as_posix()}` is unsafe.",
        )
    output_root = output.absolute()
    try:
        target.absolute().relative_to(output_root)
    except ValueError as exc:
        raise OutputCleanupError(
            "OUTPUT_PATH_UNSAFE",
            f"Managed generated output path `{relative_path.as_posix()}` escaped the output root.",
        ) from exc


def _is_junction(path: Path) -> bool:
    is_junction = getattr(path, "is_junction", None)
    return bool(is_junction and is_junction())


class OutputCleanupError(Exception):
    def __init__(self, code: str, safe_message: str, diagnostic: str | None = None) -> None:
        message = f"{code}: {safe_message}"
        if diagnostic:
            message = f"{message} Diagnostic: {diagnostic}"
        super().__init__(message)
        self.code = code
        self.safe_message = message
