"""Service catalogue: every analysed service with its description status and purpose."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from wm_doc.ir import FlowService
from wm_doc.service_docs import DocState, ServiceDoc

SERVICE_CATALOGUE = "service-catalogue.md"

STATE_LABELS = {
    DocState.APPROVED: "approved",
    DocState.STALE: "approved, facts changed",
    DocState.EDITED: "edited draft",
    DocState.DRAFT: "draft (not reviewed)",
    DocState.MISSING: "no description yet",
}


def doc_state(doc: ServiceDoc | None) -> DocState:
    return DocState.MISSING if doc is None else doc.state()


def render_service_catalogue(
    services: list[FlowService],
    docs: dict[str, ServiceDoc],
    service_filenames: dict[str, str],
) -> str:
    states = {service.identity.full_name: doc_state(docs.get(service.identity.full_name))
              for service in services}
    counts = Counter(states.values())
    lines = [
        "# Service Catalogue",
        "",
        (
            "One line per service, taken from the Purpose section of its description file. "
            "Drafts were written by a local language model and have not been reviewed."
        ),
        "",
        "| Status | Services |",
        "| --- | ---: |",
    ]
    for state in (DocState.APPROVED, DocState.STALE, DocState.EDITED, DocState.DRAFT,
                  DocState.MISSING):
        lines.append(f"| {STATE_LABELS[state]} | {counts.get(state, 0)} |")
    by_package: dict[str, list[FlowService]] = defaultdict(list)
    for service in services:
        by_package[service.identity.package].append(service)
    for package in sorted(by_package, key=str.casefold):
        lines += ["", f"## {package}", "", "| Service | Status | Purpose |", "| --- | --- | --- |"]
        for service in sorted(by_package[package], key=lambda s: s.identity.full_name.casefold()):
            name = service.identity.full_name
            doc = docs.get(name)
            filename = service_filenames.get(name)
            link = f"[`{name}`](services/{filename})" if filename else f"`{name}`"
            purpose = (doc.purpose_line() or "") if doc is not None else ""
            lines.append(f"| {link} | {STATE_LABELS[states[name]]} | {_cell(purpose)} |")
    lines.append("")
    return "\n".join(lines)


def write_service_catalogue(
    output_dir: Path,
    services: list[FlowService],
    docs: dict[str, ServiceDoc],
    service_filenames: dict[str, str],
) -> Path:
    path = output_dir / SERVICE_CATALOGUE
    path.write_text(
        render_service_catalogue(services, docs, service_filenames), encoding="utf-8"
    )
    return path


def _cell(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|")
