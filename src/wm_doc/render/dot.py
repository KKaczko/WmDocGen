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
    targets = {edge.target_service for edge in analysis.edges}
    nodes = sorted(analyzed | targets, key=str.casefold)
    lines = ["digraph dependencies {", "  rankdir=LR;"]
    for node in nodes:
        attrs = [f'label="{_escape(node)}"']
        if node in analyzed:
            attrs.append('kind="flow_service"')
        else:
            attrs.append('kind="dependency_target"')
        lines.append(f"  {_node_id(node)} [{', '.join(attrs)}];")
    for edge in sorted(
        analysis.edges,
        key=lambda item: (
            item.source_service.casefold(),
            item.invoke_id,
            item.target_service.casefold(),
        ),
    ):
        attrs = [
            'label="INVOKES"',
            f'invoke="{_escape(edge.invoke_id)}"',
            f'resolved="{str(edge.resolved).lower()}"',
        ]
        lines.append(
            f"  {_node_id(edge.source_service)} -> {_node_id(edge.target_service)} "
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
