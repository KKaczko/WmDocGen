from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from wm_doc.analysis import analyze_path
from wm_doc.config import load_config
from wm_doc.discovery import scan_path
from wm_doc.render.analysis_json import render_analysis_json
from wm_doc.render.document_markdown import write_document_markdown
from wm_doc.render.dot import write_dependency_dot, write_document_dot, write_process_dots
from wm_doc.render.index_markdown import write_documentation_index
from wm_doc.render.json import render_inventory_json
from wm_doc.render.markdown import render_inventory_markdown
from wm_doc.render.process_markdown import (
    write_entrypoint_candidates_markdown,
    write_process_markdown,
)
from wm_doc.render.service_markdown import write_service_markdown

app = typer.Typer(
    help="Offline deterministic static inventory for webMethods Integration Server packages."
)


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
) -> None:
    """Analyze supported services and emit deterministic technical outputs."""
    app_config = load_config(config)
    analysis = analyze_path(
        packages_path,
        app_config,
        processes_file,
        processes_file_explicit=processes_file is not None,
    )
    output.mkdir(parents=True, exist_ok=True)
    (output / "analysis.json").write_text(render_analysis_json(analysis), encoding="utf-8")
    services = [service for package in analysis.packages for service in package.services]
    documents = [document for package in analysis.packages for document in package.document_types]
    index_path = write_documentation_index(output, analysis)
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
    process_paths = write_process_markdown(output, analysis)
    entrypoint_path = write_entrypoint_candidates_markdown(output, analysis)
    dot_path = write_dependency_dot(output, analysis)
    document_dot_path = write_document_dot(output, analysis)
    process_dot_paths = write_process_dots(output, analysis)
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
        f"{len(process_dot_paths)} process DOT file(s)."
    )
