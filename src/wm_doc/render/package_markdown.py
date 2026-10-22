"""Package pages (`packages/<Package>.md`) and the index sections that link to them.

Each page shows the package overview file when one exists, then deterministic facts: service
counts, the services through which work enters the package, every service with its purpose
line, the data and systems the package's own services touch, and the packages it calls and is
called by.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from wm_doc.overviews import PackageSummary
from wm_doc.render.service_markdown import doc_badge, doc_body
from wm_doc.service_docs import ServiceDoc

PACKAGES_DIR = "packages"
MAX_SERVICES_PER_ROW = 5


def package_page_filenames(names: list[str]) -> dict[str, str]:
    """Package name -> page filename, disambiguating names that sanitize alike."""
    slugs = {name: re.sub(r"[^A-Za-z0-9_.-]+", "_", name) or "_" for name in names}
    counts = Counter(slug.casefold() for slug in slugs.values())
    filenames: dict[str, str] = {}
    for name, slug in slugs.items():
        if counts[slug.casefold()] > 1:
            slug = f"{slug}__{hashlib.sha256(name.encode('utf-8')).hexdigest()[:12]}"
        filenames[name] = f"{slug}.md"
    return filenames


def render_package_page(
    summary: PackageSummary,
    *,
    overview: ServiceDoc | None,
    docs_enabled: bool,
    purposes: Mapping[str, str],
    service_filenames: Mapping[str, str],
    package_filenames: Mapping[str, str],
) -> str:
    counts = summary.type_counts()
    lines = [f"# Package {summary.name}", ""]
    if overview is not None:
        lines += [doc_badge(overview), "", doc_body(overview), ""]
    elif docs_enabled:
        lines += [
            "No package overview yet. Draft one with "
            f"`wm-doc overview <packages> --package {summary.name} --model <model>`.",
            "",
        ]
    lines += [
        "## Summary",
        "",
        "| Item | Count |",
        "| --- | ---: |",
        f"| Services | {len(summary.services)} |",
        f"| FLOW services | {counts.get('FLOW', 0)} |",
        f"| Java services | {counts.get('Java', 0)} |",
        f"| Other services (adapters and other non-FLOW types) | {counts.get('other', 0)} |",
        f"| Document types | {summary.document_count} |",
        f"| Entry points | {len(summary.entries)} |",
        "",
        "## Entry Points",
        "",
        (
            "Services that work reaches from outside this package: named by a trigger, "
            "descriptor or other artifact, declared as a process entry point, called from "
            "another package, or not called by any analysed service."
        ),
        "",
    ]
    if summary.entries:
        lines += ["| Service | Reached from |", "| --- | --- |"]
        for entry in summary.entries:
            reached = "; ".join(entry.reached_from)
            lines.append(
                f"| {_service_link(entry.service, service_filenames)} | {_cell(reached)} |"
            )
    else:
        lines.append("No service in this package is reached from outside it.")
    lines += [
        "",
        "## Services",
        "",
        "Purpose lines come from the description files when present, otherwise from the "
        "generated summary.",
        "",
        "| Service | Type | Purpose |",
        "| --- | --- | --- |",
    ]
    for name in summary.services:
        lines.append(
            f"| {_service_link(name, service_filenames)} | {summary.service_types[name]} "
            f"| {_cell(purposes.get(name, ''))} |"
        )
    lines += [
        "",
        "## Data and Systems",
        "",
        "What the package's own services read, write, send or call; effects of services in "
        "other packages are listed on those packages' pages.",
        "",
    ]
    if summary.effects:
        lines += ["| Action | Object | Where | Services |", "| --- | --- | --- | --- |"]
        for row in summary.effects:
            shown = ", ".join(
                _service_link(name, service_filenames)
                for name in row.services[:MAX_SERVICES_PER_ROW]
            )
            extra = len(row.services) - MAX_SERVICES_PER_ROW
            if extra > 0:
                shown += f" and {extra} more"
            lines.append(
                f"| {_cell(row.action)} | {_cell(row.object)} | {_cell(row.where)} | {shown} |"
            )
    else:
        lines.append("No data objects or external systems were found for this package.")
    lines += [
        "",
        "## Package Dependencies",
        "",
        f"- Calls into: {_package_counts(summary.calls_into, package_filenames)}",
        f"- Called from: {_package_counts(summary.called_from, package_filenames)}",
        "",
    ]
    return "\n".join(lines)


def write_package_markdown(
    output_dir: Path,
    summaries: Mapping[str, PackageSummary],
    *,
    overviews: Mapping[str, ServiceDoc],
    docs_enabled: bool,
    purposes: Mapping[str, str],
    service_filenames: Mapping[str, str],
) -> dict[str, Path]:
    directory = output_dir / PACKAGES_DIR
    directory.mkdir(parents=True, exist_ok=True)
    filenames = package_page_filenames(list(summaries))
    paths: dict[str, Path] = {}
    for name, summary in summaries.items():
        path = directory / filenames[name]
        path.write_text(
            render_package_page(
                summary,
                overview=overviews.get(name),
                docs_enabled=docs_enabled,
                purposes=purposes,
                service_filenames=service_filenames,
                package_filenames=filenames,
            ),
            encoding="utf-8",
        )
        paths[name] = path
    return paths


def render_packages_index_section(
    summaries: Mapping[str, PackageSummary],
    overviews: Mapping[str, ServiceDoc],
    *,
    docs_enabled: bool,
) -> str:
    """The "Packages" table of index.md, with overview purpose lines when present."""
    filenames = package_page_filenames(list(summaries))
    header = "| Package | Services | Entry points |"
    rule = "| --- | ---: | ---: |"
    if docs_enabled:
        header += " Overview |"
        rule += " --- |"
    lines = ["## Packages", "", header, rule]
    for name in sorted(summaries, key=str.casefold):
        summary = summaries[name]
        row = (
            f"| [{_cell(name)}]({PACKAGES_DIR}/{filenames[name]}) | {len(summary.services)} "
            f"| {len(summary.entries)} |"
        )
        if docs_enabled:
            doc = overviews.get(name)
            row += f" {_cell(doc.purpose_line() or '') if doc is not None else 'not written'} |"
        lines.append(row)
    lines.append("")
    return "\n".join(lines)


def render_server_overview_section(doc: ServiceDoc) -> str:
    return "\n".join(["## Server Overview", "", doc_badge(doc), "", doc_body(doc), ""])


def _service_link(name: str, service_filenames: Mapping[str, str]) -> str:
    filename = service_filenames.get(name)
    return f"[`{name}`](../services/{filename})" if filename else f"`{name}`"


def _package_counts(
    counts: tuple[tuple[str, int], ...], package_filenames: Mapping[str, str]
) -> str:
    if not counts:
        return "none"
    parts = []
    for name, count in counts:
        filename = package_filenames.get(name)
        label = f"[{_cell(name)}]({filename})" if filename else f"`{name}`"
        parts.append(f"{label} ({count} call{'s' if count != 1 else ''})")
    return ", ".join(parts)


def _cell(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")
