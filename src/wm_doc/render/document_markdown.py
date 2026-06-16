from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

from wm_doc.ir import (
    DocumentDependency,
    DocumentField,
    DocumentReferenceOccurrence,
    DocumentType,
    ExtractionPolicySnapshot,
    ServiceDocumentDependency,
    TextValue,
)

MAX_FIELD_ROWS = 120


def render_document_markdown(
    document: DocumentType,
    references: list[DocumentReferenceOccurrence],
    document_dependencies: list[DocumentDependency],
    service_dependencies: list[ServiceDocumentDependency],
    extraction_policy: ExtractionPolicySnapshot,
) -> str:
    outgoing = [
        dependency
        for dependency in document_dependencies
        if dependency.source_document == document.identity.full_name
    ]
    referenced_by_documents = [
        dependency
        for dependency in document_dependencies
        if dependency.target_document == document.identity.full_name
    ]
    referenced_by_services = [
        dependency
        for dependency in service_dependencies
        if dependency.target_document == document.identity.full_name
    ]
    unresolved = [
        reference
        for reference in references
        if reference.owner_name == document.identity.full_name and not reference.resolved
    ]
    lines = [
        f"# {document.identity.full_name}",
        "",
        "## Identity",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Package | `{document.identity.package}` |",
        f"| Namespace | `{document.identity.namespace}` |",
        f"| Document | `{document.identity.name}` |",
        f"| Basis | `{document.identity.basis}` |",
        f"| Declared package | `{document.identity.declared_package or ''}` |",
        "",
        "## Description",
        "",
        _text_display(document.description) or "No description was declared in supported metadata.",
        "",
        "## Field Hierarchy",
        "",
        _render_fields(document.fields),
        "",
        "## Document References",
        "",
        _render_document_dependencies(outgoing),
        "",
        "## Referenced By Services",
        "",
        _render_service_dependencies(referenced_by_services),
        "",
        "## Referenced By Documents",
        "",
        _render_document_dependencies(referenced_by_documents, reverse=True),
        "",
        "## Unresolved References",
        "",
        _render_unresolved(unresolved),
        "",
        "## Disclosure Policies",
        "",
        _render_policy(extraction_policy),
        "",
        "## Findings",
        "",
        _render_findings(document),
        "",
        "## Source Evidence",
        "",
        f"- Document metadata: `{document.source.path}`"
        + (f":{document.source.line}" if document.source.line else ""),
        "",
        "## Analysis Limitations",
        "",
        (
            "M3 extracts technical Document Type structure and document-reference evidence. "
            "It does not validate mapping paths against schemas, infer business meaning, "
            "or expand referenced documents recursively."
        ),
        "",
    ]
    return "\n".join(lines)


def document_markdown_filename(full_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", full_name)
    return f"{slug}.md"


def write_document_markdown(
    output_dir: Path,
    documents: list[DocumentType],
    references: list[DocumentReferenceOccurrence],
    document_dependencies: list[DocumentDependency],
    service_dependencies: list[ServiceDocumentDependency],
    extraction_policy: ExtractionPolicySnapshot,
) -> list[Path]:
    document_dir = output_dir / "documents"
    document_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    slug_counts = Counter(
        document_markdown_filename(document.identity.full_name) for document in documents
    )
    for document in sorted(documents, key=lambda item: item.identity.full_name.casefold()):
        filename = document_markdown_filename(document.identity.full_name)
        if slug_counts[filename] > 1:
            stem = filename.removesuffix(".md")
            digest = hashlib.sha256(document.identity.full_name.encode("utf-8")).hexdigest()[:12]
            filename = f"{stem}__{digest}.md"
        path = document_dir / filename
        path.write_text(
            render_document_markdown(
                document,
                references,
                document_dependencies,
                service_dependencies,
                extraction_policy,
            ),
            encoding="utf-8",
        )
        written.append(path)
    return written


def _render_fields(fields: list[DocumentField]) -> str:
    if not fields:
        return "No fields declared in supported metadata.\n"
    lines = [
        "| Field | Type | Dimension | Optional | Document Reference | Source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    rows = 0

    def visit(field: DocumentField, depth: int) -> None:
        nonlocal rows
        if rows >= MAX_FIELD_ROWS:
            return
        rows += 1
        indent = "  " * depth
        source = field.source.path + (f":{field.source.line}" if field.source.line else "")
        lines.append(
            "| "
            f"`{indent}{field.name}` | "
            f"`{field.raw_field_type or ''}` | "
            f"`{field.raw_dimension or ''}` / `{field.dimension.value}` | "
            f"{field.optional if field.optional is not None else ''} | "
            f"`{field.document_reference or ''}` | "
            f"`{source}` |"
        )
        for child in field.children:
            visit(child, depth + 1)

    for field in fields:
        visit(field, 0)
    if rows >= MAX_FIELD_ROWS:
        lines.append(
            f"| ... | ... | ... | ... | ... | field list truncated at {MAX_FIELD_ROWS} rows |"
        )
    return "\n".join(lines) + "\n"


def _render_document_dependencies(
    dependencies: list[DocumentDependency], *, reverse: bool = False
) -> str:
    if not dependencies:
        return "No document dependencies were extracted.\n"
    lines = ["| Document | Resolved | Occurrences |", "| --- | --- | ---: |"]
    for dependency in sorted(
        dependencies,
        key=lambda item: (
            item.source_document.casefold(),
            item.target_document.casefold(),
            item.id,
        ),
    ):
        other = dependency.source_document if reverse else dependency.target_document
        lines.append(f"| `{other}` | {dependency.resolved} | {dependency.occurrence_count} |")
    return "\n".join(lines) + "\n"


def _render_service_dependencies(dependencies: list[ServiceDocumentDependency]) -> str:
    if not dependencies:
        return "No service-document dependencies were extracted.\n"
    lines = ["| Service | Usage | Resolved | Occurrences |", "| --- | --- | --- | ---: |"]
    for dependency in sorted(
        dependencies,
        key=lambda item: (item.service.casefold(), item.usage_role.value, item.id),
    ):
        lines.append(
            "| "
            f"`{dependency.service}` | "
            f"`{dependency.usage_role.value}` | "
            f"{dependency.resolved} | "
            f"{dependency.occurrence_count} |"
        )
    return "\n".join(lines) + "\n"


def _render_unresolved(references: list[DocumentReferenceOccurrence]) -> str:
    if not references:
        return "No unresolved document references were extracted for this document.\n"
    lines = ["| Field | Target | Source |", "| --- | --- | --- |"]
    for reference in sorted(references, key=lambda item: item.source_field_path.casefold()):
        source = reference.source.path + (
            f":{reference.source.line}" if reference.source.line else ""
        )
        lines.append(
            f"| `{reference.source_field_path}` | `{reference.declared_target}` | `{source}` |"
        )
    return "\n".join(lines) + "\n"


def _render_policy(policy: ExtractionPolicySnapshot) -> str:
    secret_guard = "enabled" if policy.secret_guard.enabled else "disabled"
    return (
        f"- Free text mode: {policy.free_text_mode}\n"
        f"- Literal mode: {policy.literal_mode}\n"
        f"- Secret guard: {secret_guard}\n"
        f"- Secret guard strategy: {policy.secret_guard.strategy_version}\n"
    )


def _render_findings(document: DocumentType) -> str:
    if not document.findings:
        return "No document-level findings.\n"
    lines = []
    for finding in document.findings:
        severity = f"{finding.severity} " if finding.severity else ""
        lines.append(
            f"- {severity}{finding.status} `{finding.code}` at "
            f"`{finding.source.path}`: {finding.message}"
        )
    return "\n".join(lines) + "\n"


def _text_display(text: TextValue | None) -> str | None:
    if text is None:
        return None
    if text.value:
        return text.value
    if text.marker:
        return text.marker
    return None
