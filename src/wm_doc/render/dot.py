from __future__ import annotations

import hashlib
from pathlib import Path

from wm_doc.ir import AnalysisResult


def render_dependency_dot(analysis: AnalysisResult) -> str:
    analyzed = {
        service.identity.full_name
        for package in analysis.packages
        for service in package.services
    }
    targets = {dependency.target_service for dependency in analysis.unique_dependencies}
    nodes = sorted(analyzed | targets, key=str.casefold)
    lines = ["digraph dependencies {", "  rankdir=LR;"]
    for node in nodes:
        attrs = [f'label="{_escape(node)}"']
        if node in analyzed:
            attrs.append('kind="flow_service"')
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


def _node_id(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"n_{digest}"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
