from __future__ import annotations

from pathlib import Path

from wm_doc.graph_publish import GraphAsset


def render_graph_index(assets: list[GraphAsset]) -> str:
    lines = [
        "# Graph Catalog",
        "",
        "DOT files are the canonical graph outputs. SVG and PNG files are derived views.",
        "",
        "| Graph | Scope | DOT | SVG | PNG |",
        "| --- | --- | --- | --- | --- |",
    ]
    for asset in sorted(assets, key=lambda item: item.dot_path.casefold()):
        lines.append(
            "| "
            f"{asset.title} | "
            f"`{asset.scope}` | "
            f"{_link('DOT', _graph_index_relative(asset.dot_path))} | "
            f"{_rendered_link(asset, 'svg')} | "
            f"{_rendered_link(asset, 'png')} |"
        )
    if not assets:
        lines.append("| No graphs generated |  |  |  |  |")
    lines.append("")
    return "\n".join(lines)


def write_graph_index(output_dir: Path, assets: list[GraphAsset]) -> Path:
    graph_dir = output_dir / "graphs"
    graph_dir.mkdir(parents=True, exist_ok=True)
    path = graph_dir / "index.md"
    path.write_text(render_graph_index(assets), encoding="utf-8")
    return path


def _rendered_link(asset: GraphAsset, suffix: str) -> str:
    path = asset.rendered_paths.get(suffix)
    if path is None:
        return ""
    return _link(suffix.upper(), _graph_index_relative(path))


def _graph_index_relative(path: str) -> str:
    return Path(path).relative_to("graphs").as_posix()


def _link(label: str, path: str) -> str:
    return f"[{label}]({path})"
