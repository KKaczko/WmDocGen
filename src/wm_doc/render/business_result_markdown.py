from __future__ import annotations

from pathlib import Path

from wm_doc.business_enrichment import (
    BusinessEnrichmentError,
    assert_business_result_text_safe,
    render_business_result_json,
)
from wm_doc.business_result_schema import BusinessEnrichmentErrorCode, BusinessResult


def render_business_result_markdown(result: BusinessResult) -> str:
    lines = [
        "# Business Enrichment",
        "",
        (
            "This page is generated from an application-owned `business-result.v1` built from a "
            "validated structured model draft. Claims are model-authored and evidence-checked "
            "against `business-context.v1`; they are not canonical technical analysis."
        ),
        "",
        "## Identity",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Schema | `{result.schema_version}` |",
        f"| Result ID | `{result.result_id}` |",
        f"| Context ID | `{result.context_id}` |",
        f"| Context kind | `{result.context_kind.value}` |",
        f"| Status | `{result.status.value}` |",
        f"| Language | `{result.language.value}` |",
        f"| Source context SHA-256 | `{result.source_context_sha256}` |",
        "",
        "## Provenance",
        "",
        _render_provenance(result.provenance),
        "",
        "## Claims",
        "",
        _render_claims(result),
        "",
        "## Unknowns",
        "",
        _render_unknowns(result),
        "",
        "## Limitations",
        "",
        _render_limitations(result),
        "",
        "## Conflicts",
        "",
        _render_conflicts(result),
        "",
        "## Validation",
        "",
        _render_validation(result.validation),
        "",
    ]
    return "\n".join(lines)


def write_business_result_outputs(output_dir: Path, result: BusinessResult) -> list[Path]:
    if output_dir.exists() and (output_dir.is_file() or output_dir.is_symlink()):
        raise BusinessEnrichmentError(
            BusinessEnrichmentErrorCode.OUTPUT_FAILED,
            "Business enrichment output path must be a directory.",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    json_text = render_business_result_json(result)
    markdown_text = render_business_result_markdown(result)
    assert_business_result_text_safe(json_text)
    assert_business_result_text_safe(markdown_text)
    json_path = output_dir / "result.json"
    markdown_path = output_dir / "index.md"
    _publish_bundle({json_path: json_text, markdown_path: markdown_text})
    return [json_path, markdown_path]


def _render_provenance(provenance: dict[str, object]) -> str:
    rows = ["| Field | Value |", "| --- | --- |"]
    for key in (
        "provider",
        "model",
        "model_digest",
        "ollama_version",
        "prompt_version",
        "draft_schema_version",
        "schema_version",
        "result_schema_version",
        "temperature",
        "stream",
        "num_predict",
        "attempt_count",
        "cache_hit",
        "request_bytes",
    ):
        value = provenance.get(key, "")
        rows.append(f"| {key.replace('_', ' ').title()} | `{_escape(str(value))}` |")
    metrics = provenance.get("metrics")
    if isinstance(metrics, dict):
        for key in sorted(metrics):
            rows.append(f"| Metric {key} | `{_escape(str(metrics[key]))}` |")
    return "\n".join(rows)


def _render_claims(result: BusinessResult) -> str:
    if not result.claims:
        return "No business claims were generated.\n"
    lines: list[str] = []
    for section in sorted({claim.section for claim in result.claims}, key=lambda item: item.value):
        lines.extend([f"### {section.value.title()}", ""])
        lines.extend(
            [
                "| Confidence | Claim | Evidence |",
                "| --- | --- | --- |",
            ]
        )
        for claim in [item for item in result.claims if item.section == section]:
            evidence = ", ".join(f"`{_escape(evidence_id)}`" for evidence_id in claim.evidence_ids)
            lines.append(
                f"| `{claim.confidence.value}` | {_escape(claim.text)} | {evidence or 'none'} |"
            )
        lines.append("")
    return "\n".join(lines)


def _render_unknowns(result: BusinessResult) -> str:
    if not result.unknowns:
        return "No model-reported unknowns.\n"
    rows = ["| Code | Summary | Evidence |", "| --- | --- | --- |"]
    for item in result.unknowns:
        evidence = ", ".join(f"`{_escape(evidence_id)}`" for evidence_id in item.evidence_ids)
        rows.append(f"| `{_escape(item.code)}` | {_escape(item.summary)} | {evidence or 'none'} |")
    return "\n".join(rows) + "\n"


def _render_limitations(result: BusinessResult) -> str:
    if not result.limitations:
        return "No business enrichment limitations were reported.\n"
    rows = ["| Code | Summary | Evidence |", "| --- | --- | --- |"]
    for item in result.limitations:
        evidence = ", ".join(f"`{_escape(evidence_id)}`" for evidence_id in item.evidence_ids)
        rows.append(f"| `{_escape(item.code)}` | {_escape(item.summary)} | {evidence or 'none'} |")
    return "\n".join(rows) + "\n"


def _render_conflicts(result: BusinessResult) -> str:
    if not result.conflicts:
        return "No conflicts were reported.\n"
    rows = ["| Severity | Description | Evidence |", "| --- | --- | --- |"]
    for item in result.conflicts:
        evidence = ", ".join(f"`{_escape(evidence_id)}`" for evidence_id in item.evidence_ids)
        rows.append(
            f"| `{item.severity.value}` | {_escape(item.description)} | {evidence or 'none'} |"
        )
    return "\n".join(rows) + "\n"


def _render_validation(validation: dict[str, object]) -> str:
    rows = ["| Field | Value |", "| --- | --- |"]
    for key in sorted(validation):
        rows.append(f"| {key.replace('_', ' ').title()} | `{_escape(str(validation[key]))}` |")
    return "\n".join(rows) + "\n"


def _publish_bundle(contents: dict[Path, str]) -> None:
    paths = list(contents)
    for path in paths:
        if path.exists() and path.is_dir() and not path.is_symlink():
            raise BusinessEnrichmentError(
                BusinessEnrichmentErrorCode.OUTPUT_FAILED,
                f"Managed output path `{path.name}` is a directory.",
            )
    temp_paths = {path: path.with_name(f".{path.name}.tmp") for path in paths}
    backup_paths = {path: path.with_name(f".{path.name}.bak") for path in paths}
    backups_created = {path: False for path in paths}
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
            _restore_bundle(paths, backup_paths, backups_created)
            restored = True
            raise
    except OSError as exc:
        if not restored:
            _restore_bundle(paths, backup_paths, backups_created)
        _cleanup_temp_files(temp_paths, backup_paths)
        raise BusinessEnrichmentError(
            BusinessEnrichmentErrorCode.OUTPUT_FAILED,
            "Could not publish complete business enrichment bundle.",
        ) from exc
    _cleanup_temp_files(temp_paths, backup_paths)


def _restore_bundle(
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


def _cleanup_temp_files(temp_paths: dict[Path, Path], backup_paths: dict[Path, Path]) -> None:
    for path in [*temp_paths.values(), *backup_paths.values()]:
        try:
            if path.exists() or path.is_symlink():
                if path.is_dir() and not path.is_symlink():
                    continue
                path.unlink()
        except OSError:
            pass


def _escape(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
