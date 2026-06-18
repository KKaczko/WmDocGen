from __future__ import annotations

from pathlib import Path

from wm_doc.ir import AnalysisResult


def render_documentation_index(analysis: AnalysisResult) -> str:
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
        "- [Service dependency graph](graphs/dependencies.dot)",
        "- [Document dependency graph](graphs/documents.dot)",
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


def write_documentation_index(output_dir: Path, analysis: AnalysisResult) -> Path:
    path = output_dir / "index.md"
    path.write_text(render_documentation_index(analysis), encoding="utf-8")
    return path
