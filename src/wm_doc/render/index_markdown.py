from __future__ import annotations

from pathlib import Path

from wm_doc.graph_publish import GraphAsset
from wm_doc.ir import AnalysisResult


def render_documentation_index(
    analysis: AnalysisResult, graph_assets: list[GraphAsset] | None = None
) -> str:
    graph_assets = graph_assets or []
    lines = [
        "# wm-doc Technical Documentation",
        "",
        (
            "This index is generated from static analysis. Process names and "
            "descriptions, when present, come from `processes.yml`."
        ),
        "",
        "## Generated Inventory",
        "",
        "| Area | Count |",
        "| --- | ---: |",
        f"| Services | {sum(len(package.services) for package in analysis.packages)} |",
        f"| Document Types | {len(analysis.document_types)} |",
        f"| Process definitions | {len(analysis.processes)} |",
        f"| Technical entrypoint candidates | {len(analysis.technical_entrypoint_candidates)} |",
        f"| Service dependency edges | {len(analysis.unique_dependencies)} |",
        f"| Document dependency edges | {len(analysis.document_dependencies)} |",
        "",
        "## Links",
        "",
        "- [Analysis JSON](analysis.json)",
        "- [Graph catalog](graphs/index.md)",
        f"- Service dependency graph: {_graph_link(graph_assets, 'graphs/dependencies.dot')}",
        f"- Document dependency graph: {_graph_link(graph_assets, 'graphs/documents.dot')}",
        "- [Technical entrypoint candidates](entrypoints.md)",
        "- [Services](services/)",
        "- [Document Types](documents/)",
    ]
    if analysis.processes:
        lines.append("- [Process catalog](processes/index.md)")
        lines.append("- [Process graphs](graphs/processes/)")
    else:
        lines.append("- Process catalog: no process definitions were declared.")
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
                "Process membership is generated from declared entrypoints and static service "
                "dependency evidence. The tool does not infer business meaning, runtime order, "
                "JDBC/UM/JMS resources, trigger behavior, scheduler behavior, or deep Java effects."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_documentation_index(
    output_dir: Path, analysis: AnalysisResult, graph_assets: list[GraphAsset] | None = None
) -> Path:
    path = output_dir / "index.md"
    path.write_text(render_documentation_index(analysis, graph_assets), encoding="utf-8")
    return path


def _graph_link(graph_assets: list[GraphAsset], dot_path: str) -> str:
    asset = next((item for item in graph_assets if item.dot_path == dot_path), None)
    if asset is None:
        return f"[DOT]({dot_path})"
    if "svg" in asset.rendered_paths:
        return f"[SVG]({asset.rendered_paths['svg']}) ([DOT]({asset.dot_path}))"
    if "png" in asset.rendered_paths:
        return f"[PNG]({asset.rendered_paths['png']}) ([DOT]({asset.dot_path}))"
    return f"[DOT]({asset.dot_path})"
