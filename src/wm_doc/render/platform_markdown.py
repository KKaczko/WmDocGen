"""Page listing the platform (`pub.*`, `wm.*`) services the analysed code calls."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from wm_doc.builtins import builtin_effect, is_builtin_name
from wm_doc.ir import AnalysisResult
from wm_doc.render.service_markdown import service_markdown_filename

PLATFORM_MARKDOWN = "platform-services.md"
MAX_CALLERS_SHOWN = 5


def platform_callers(analysis: AnalysisResult) -> dict[str, set[str]]:
    """Platform service -> the analysed services that call it."""
    callers: dict[str, set[str]] = defaultdict(set)
    for service in analysis.services:
        for dependency in service.unique_dependencies:
            if is_builtin_name(dependency.target_service):
                callers[dependency.target_service].add(service.identity.full_name)
    return callers


def render_platform_services(analysis: AnalysisResult) -> str:
    callers = platform_callers(analysis)
    ranked = sorted(callers, key=lambda name: (-len(callers[name]), name.casefold()))
    described = [name for name in ranked if builtin_effect(name) is not None]
    missing = [name for name in ranked if builtin_effect(name) is None]
    lines = [
        "# Platform Services",
        "",
        (
            "Services from the product packages (WmPublic, WmART, WmJDBCAdapter, ...) that the "
            "analysed code calls, with the description wm-doc uses for them. Add or override "
            "descriptions with `--platform-services <file>`."
        ),
        "",
        f"- Platform services called: {len(ranked)}",
        f"- With a description: {len(described)}",
        f"- Without a description: {len(missing)}",
        "",
        "## Described",
        "",
    ]
    if described:
        lines += [
            "| Service | What it does | Family | Callers | Called by |",
            "| --- | --- | --- | ---: | --- |",
        ]
        for name in described:
            effect = builtin_effect(name)
            assert effect is not None
            lines.append(
                f"| `{name}` | {effect.label} | `{effect.family.value}` | "
                f"{len(callers[name])} | {_callers(callers[name])} |"
            )
    else:
        lines.append("None.")
    lines += ["", "## Without a description", ""]
    if missing:
        lines += ["| Service | Callers | Called by |", "| --- | ---: | --- |"]
        lines += [
            f"| `{name}` | {len(callers[name])} | {_callers(callers[name])} |" for name in missing
        ]
    else:
        lines.append("None: every platform service the code calls has a description.")
    lines.append("")
    return "\n".join(lines)


def _callers(names: set[str]) -> str:
    ordered = sorted(names, key=str.casefold)
    shown = ", ".join(
        f"[`{name}`](services/{service_markdown_filename(name)})"
        for name in ordered[:MAX_CALLERS_SHOWN]
    )
    extra = len(ordered) - MAX_CALLERS_SHOWN
    return shown + (f" and {extra} more" if extra > 0 else "")


def write_platform_services(output_dir: Path, analysis: AnalysisResult) -> Path:
    path = output_dir / PLATFORM_MARKDOWN
    path.write_text(render_platform_services(analysis), encoding="utf-8")
    return path
