from __future__ import annotations

import json
from pathlib import Path

from wm_doc.business_context import (
    MAX_CONTEXT_JSON_BYTES,
    BusinessContextError,
    assert_business_context_text_safe,
)
from wm_doc.business_context_schema import BusinessContext, BusinessContextErrorCode


def render_business_context_json(context: BusinessContext) -> str:
    payload = context.model_dump(mode="json", exclude_none=True)
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_business_context_markdown(context: BusinessContext) -> str:
    lines = [
        "# Business Context Preview",
        "",
        (
            "This file is a deterministic context preview for human review. It is not "
            "LLM-generated business documentation and does not contain generated business claims."
        ),
        "",
        "## Identity",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Schema | `{context.schema_version}` |",
        f"| Context ID | `{context.context_id}` |",
        f"| Kind | `{context.context_kind.value}` |",
        f"| Status | `{context.status.value}` |",
        f"| Status reasons | `{', '.join(context.status_reasons) or 'none'}` |",
        "",
        "## Source",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Analysis schema | `{context.source.get('analysis_schema', '')}` |",
        f"| Scope schema | `{context.source.get('scope_schema', '')}` |",
        f"| Analysis SHA-256 | `{context.source.get('analysis_sha256', '')}` |",
        f"| Scope SHA-256 | `{context.source.get('scope_sha256', '')}` |",
        f"| Builder version | `{context.source.get('builder_version', '')}` |",
        f"| Profile | `{context.source.get('context_profile', '')}` |",
        "",
        "## Subject",
        "",
        _render_subject(context.subject),
        "",
        "## Approved Metadata",
        "",
        _render_approved_metadata(context.approved_metadata),
        "",
        "## Technical Summary",
        "",
        _render_summary(context.technical_summary),
        "",
        "## Technical Stages",
        "",
        _render_stages(context.technical_stages),
        "",
        "## Services",
        "",
        _render_services(context.services),
        "",
        "## Documents",
        "",
        _render_documents(context.documents),
        "",
        "## Dependencies",
        "",
        _render_dependencies(context.dependencies),
        "",
        "## Boundaries And Unknowns",
        "",
        _render_boundaries(context.boundaries),
        "",
        _render_unknowns(context.unknowns),
        "",
        "## Omissions",
        "",
        _render_omissions(context.omissions),
        "",
        "## Evidence Catalog",
        "",
        f"Evidence records: {len(context.evidence)}",
        "",
        "Every referenced evidence ID in this context is emitted in `context.json`.",
        "",
    ]
    return "\n".join(lines)


def write_business_context_outputs(output_dir: Path, context: BusinessContext) -> list[Path]:
    if output_dir.exists() and (output_dir.is_file() or output_dir.is_symlink()):
        raise BusinessContextError(
            BusinessContextErrorCode.OUTPUT_FAILED,
            "Business context output path must be a directory.",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_text = render_business_context_json(context)
    markdown_text = render_business_context_markdown(context)
    if len(json_text.encode("utf-8")) > MAX_CONTEXT_JSON_BYTES:
        raise BusinessContextError(
            BusinessContextErrorCode.OUTPUT_FAILED,
            "Generated context.json exceeded the standard profile byte limit.",
        )
    assert_business_context_text_safe(json_text)
    assert_business_context_text_safe(markdown_text)
    json_path = output_dir / "context.json"
    markdown_path = output_dir / "context.md"
    _publish_context_bundle(
        {
            json_path: json_text,
            markdown_path: markdown_text,
        }
    )
    return [json_path, markdown_path]


def _render_subject(subject: dict[str, object]) -> str:
    selector = subject.get("selector")
    rows = [
        "| Field | Value |",
        "| --- | --- |",
        f"| Context kind | `{subject.get('context_kind', '')}` |",
    ]
    if isinstance(selector, dict):
        rows.extend(
            [
                f"| Selector type | `{selector.get('selector_type', '')}` |",
                f"| Selector value | `{_escape_table(str(selector.get('value', '')))}` |",
                f"| Dependency depth | `{selector.get('dependency_depth', '')}` |",
            ]
        )
    roots = subject.get("root_services")
    if isinstance(roots, list):
        rows.append(f"| Root services | {len(roots)} |")
    process = subject.get("process")
    if isinstance(process, dict):
        rows.append(f"| Process | `{_escape_table(str(process.get('process_id', '')))}` |")
        rows.append(f"| Process name | `{_escape_table(str(process.get('name', '')))}` |")
    service = subject.get("service")
    if service:
        rows.append(f"| Service | `{_escape_table(str(service))}` |")
    return "\n".join(rows)


def _render_approved_metadata(metadata: dict[str, object]) -> str:
    process = metadata.get("process")
    if not isinstance(process, dict):
        return "No approved business metadata is included for this context.\n"
    description = process.get("description") or ""
    rows = [
        "| Field | Value |",
        "| --- | --- |",
        f"| Process ID | `{_escape_table(str(process.get('process_id', '')))}` |",
        f"| Name | `{_escape_table(str(process.get('name', '')))}` |",
        f"| Description status | `{process.get('description_status', '')}` |",
        f"| Description | {_escape_table(str(description)) or 'not provided'} |",
    ]
    return "\n".join(rows) + "\n"


def _render_summary(summary: dict[str, object]) -> str:
    rows = ["| Area | Count |", "| --- | ---: |"]
    full = summary.get("full_snapshot")
    if isinstance(full, dict):
        for key in sorted(full):
            rows.append(f"| Full {key.replace('_', ' ')} | {full[key]} |")
    scoped = summary.get("published_scope")
    if isinstance(scoped, dict):
        for key in sorted(scoped):
            rows.append(f"| Scoped {key.replace('_', ' ')} | {scoped[key]} |")
    groups = summary.get("service_groups")
    if isinstance(groups, dict):
        for key in sorted(groups):
            rows.append(f"| Service group {key} | {groups[key]} |")
    return "\n".join(rows) + "\n"


def _render_stages(stages: list[dict[str, object]]) -> str:
    if not stages:
        return "No technical stages were derived.\n"
    rows = [
        "| Stage | Service Count | Sample Services |",
        "| ---: | ---: | --- |",
    ]
    for stage in stages:
        services = stage.get("services")
        sample = (
            ", ".join(f"`{item}`" for item in services[:5])
            if isinstance(services, list)
            else ""
        )
        omitted = stage.get("services_omitted")
        suffix = f" ({omitted} omitted)" if omitted else ""
        rows.append(
            f"| {stage.get('stage', '')} | "
            f"{stage.get('service_count', 0)} | "
            f"{sample}{suffix} |"
        )
    return "\n".join(rows) + "\n"


def _render_services(services: list[dict[str, object]]) -> str:
    if not services:
        return "No services are included in the context preview.\n"
    rows = [
        "| Service | Group | Type | Depth | Root |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for service in services:
        rows.append(
            "| "
            f"`{_escape_table(str(service.get('service', '')))}` | "
            f"`{service.get('group', '')}` | "
            f"`{service.get('service_type', '')}` | "
            f"{service.get('minimum_depth', '')} | "
            f"{service.get('is_root', '')} |"
        )
    return "\n".join(rows) + "\n"


def _render_documents(documents: list[dict[str, object]]) -> str:
    if not documents:
        return "No document types are included in this context.\n"
    rows = [
        "| Document | Direct | Fields | Depth |",
        "| --- | --- | ---: | ---: |",
    ]
    for document in documents:
        rows.append(
            "| "
            f"`{_escape_table(str(document.get('document', '')))}` | "
            f"{document.get('direct', '')} | "
            f"{document.get('field_count', 0)} | "
            f"{document.get('minimum_document_depth', '')} |"
        )
    return "\n".join(rows) + "\n"


def _render_dependencies(dependencies: list[dict[str, object]]) -> str:
    if not dependencies:
        return "No inside-scope resolved dependencies are included in this context.\n"
    rows = [
        "| Source | Kind | Target | Occurrences |",
        "| --- | --- | --- | ---: |",
    ]
    for dependency in dependencies:
        rows.append(
            "| "
            f"`{_escape_table(str(dependency.get('source_service', '')))}` | "
            f"`{dependency.get('dependency_kind', '')}` | "
            f"`{_escape_table(str(dependency.get('target_service', '')))}` | "
            f"{dependency.get('occurrence_count', 0)} |"
        )
    return "\n".join(rows) + "\n"


def _render_boundaries(boundaries: list[dict[str, object]]) -> str:
    if not boundaries:
        return "No scope boundaries are included in this context.\n"
    rows = [
        "| Status | Source | Target | Occurrences |",
        "| --- | --- | --- | ---: |",
    ]
    for boundary in boundaries:
        rows.append(
            "| "
            f"`{boundary.get('status', '')}` | "
            f"`{_escape_table(str(boundary.get('source', '')))}` | "
            f"`{_escape_table(str(boundary.get('target', '')))}` | "
            f"{boundary.get('occurrence_count', 0)} |"
        )
    return "\n".join(rows) + "\n"


def _render_unknowns(unknowns: list[dict[str, object]]) -> str:
    if not unknowns:
        return "No unresolved unknowns are included beyond listed limitations.\n"
    rows = ["| Code | Summary |", "| --- | --- |"]
    for unknown in unknowns:
        rows.append(
            f"| `{unknown.get('code', '')}` | {_escape_table(str(unknown.get('summary', '')))} |"
        )
    return "\n".join(rows) + "\n"


def _render_omissions(omissions: dict[str, object]) -> str:
    if not omissions:
        return "No deterministic context limits omitted records.\n"
    rows = ["| Section | Included | Total | Omitted |", "| --- | ---: | ---: | ---: |"]
    for section in sorted(omissions):
        value = omissions[section]
        if not isinstance(value, dict):
            continue
        rows.append(
            "| "
            f"`{_escape_table(section)}` | "
            f"{value.get('included', 0)} | "
            f"{value.get('total', 0)} | "
            f"{value.get('omitted', 0)} |"
        )
    return "\n".join(rows) + "\n"


def _publish_context_bundle(contents: dict[Path, str]) -> None:
    paths = list(contents)
    for path in paths:
        if path.exists() and path.is_dir() and not path.is_symlink():
            raise BusinessContextError(
                BusinessContextErrorCode.OUTPUT_FAILED,
                f"Managed output path `{path.name}` is a directory.",
            )

    temp_paths = {path: path.with_name(f".{path.name}.tmp") for path in paths}
    backup_paths = {path: path.with_name(f".{path.name}.bak") for path in paths}
    backups_created: dict[Path, bool] = {path: False for path in paths}
    restored = False
    try:
        for path in [*temp_paths.values(), *backup_paths.values()]:
            if path.exists() and path.is_dir() and not path.is_symlink():
                raise OSError(f"managed temporary path {path.name} is a directory")
            if path.exists() or path.is_symlink():
                path.unlink()
        for path, text in contents.items():
            temp_paths[path].write_text(text, encoding="utf-8")

        for path in paths:
            if path.exists() or path.is_symlink():
                path.replace(backup_paths[path])
                backups_created[path] = True

        try:
            for path in paths:
                temp_paths[path].replace(path)
        except OSError:
            _restore_context_bundle(paths, backup_paths, backups_created)
            restored = True
            raise
    except OSError as exc:
        if not restored:
            _restore_context_bundle(paths, backup_paths, backups_created)
        _cleanup_context_bundle_temp_files(temp_paths, backup_paths)
        raise BusinessContextError(
            BusinessContextErrorCode.OUTPUT_FAILED,
            "Could not publish complete business context bundle.",
        ) from exc
    _cleanup_context_bundle_temp_files(temp_paths, backup_paths)


def _restore_context_bundle(
    paths: list[Path],
    backup_paths: dict[Path, Path],
    backups_created: dict[Path, bool],
) -> None:
    for path in reversed(paths):
        try:
            if path.exists() or path.is_symlink():
                if path.is_dir() and not path.is_symlink():
                    continue
                path.unlink()
            if backups_created[path] and (
                backup_paths[path].exists() or backup_paths[path].is_symlink()
            ):
                backup_paths[path].replace(path)
        except OSError:
            pass


def _cleanup_context_bundle_temp_files(
    temp_paths: dict[Path, Path],
    backup_paths: dict[Path, Path],
) -> None:
    for path in [*temp_paths.values(), *backup_paths.values()]:
        try:
            if path.exists() or path.is_symlink():
                if path.is_dir() and not path.is_symlink():
                    continue
                path.unlink()
        except OSError:
            pass


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
