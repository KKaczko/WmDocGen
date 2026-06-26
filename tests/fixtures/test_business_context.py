from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from wm_doc.business_context import (
    BusinessContextError,
    build_business_context,
    load_business_context_inputs,
)
from wm_doc.business_context_schema import BusinessContextErrorCode, BusinessEvidenceType
from wm_doc.cli import app
from wm_doc.render.business_context_markdown import write_business_context_outputs


def test_build_business_context_from_service_scope(tmp_path) -> None:
    published = tmp_path / "published"
    _run_analyze(
        [
            "analyze",
            str(_samples()),
            "--output",
            str(published),
            "--target-service",
            "pgp.services.common:readConfig",
            "--dependency-depth",
            "1",
        ]
    )
    output = tmp_path / "business-context"
    (output / "keep.txt").parent.mkdir(parents=True)
    (output / "keep.txt").write_text("preserve me", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["build-business-context", "--input", str(published), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert "schema: business-context.v1" in result.output
    assert (output / "keep.txt").read_text(encoding="utf-8") == "preserve me"
    context_text = (output / "context.json").read_text(encoding="utf-8")
    context = json.loads(context_text)
    assert context["schema_version"] == "business-context.v1"
    assert context["context_kind"] == "SERVICE"
    assert context["status"] == "COMPLETE"
    assert context["status_reasons"] == []
    assert context["source"]["analysis_schema"] == "analysis.v8"
    assert context["source"]["scope_schema"] == "scope.v1"
    assert context["source"]["analysis_sha256"] == _sha256(published / "analysis.json")
    assert context["source"]["scope_sha256"] == _sha256(published / "scope.json")
    assert context["subject"]["service"] == "pgp.services.common:readConfig"
    assert context["services"]
    assert context["documents"]
    assert any(boundary["status"] == "EXTERNAL_BUILTIN" for boundary in context["boundaries"])
    assert "provider" not in context
    assert "model" not in context
    assert "prompt" not in context
    assert "cache" not in context_text
    assert "Ollama" not in context_text
    assert "runtime order" in context_text
    assert "business steps" not in context_text.lower()
    _assert_evidence_references_resolve(context)

    preview = (output / "context.md").read_text(encoding="utf-8")
    assert "deterministic context preview" in preview
    assert "not LLM-generated business documentation" in preview


def test_business_context_explicit_paths_are_deterministic(tmp_path) -> None:
    published = tmp_path / "published"
    _run_analyze(
        [
            "analyze",
            str(_samples()),
            "--output",
            str(published),
            "--target-package",
            "PGP",
            "--dependency-depth",
            "1",
        ]
    )
    outputs = [tmp_path / "ctx-a", tmp_path / "ctx-b"]
    for output in outputs:
        result = CliRunner().invoke(
            app,
            [
                "build-business-context",
                "--analysis",
                str(published / "analysis.json"),
                "--scope",
                str(published / "scope.json"),
                "--output",
                str(output),
            ],
        )
        assert result.exit_code == 0, result.output

    assert (outputs[0] / "context.json").read_bytes() == (
        outputs[1] / "context.json"
    ).read_bytes()
    assert (outputs[0] / "context.md").read_bytes() == (
        outputs[1] / "context.md"
    ).read_bytes()
    context = json.loads((outputs[0] / "context.json").read_text(encoding="utf-8"))
    assert context["context_kind"] == "SCOPE_SUMMARY"


def test_business_context_partial_process_scope_still_emits_context(tmp_path) -> None:
    processes_file = tmp_path / "processes.yml"
    processes_file.write_text(
        """version: 1
processes:
  - id: pgp-key-lookup
    name: PGP key lookup
    description: Looks up configured PGP key material.
    entrypoints:
      - pgp.services.registry:getPubKey
      - pgp.services.registry:missingKeyService
""",
        encoding="utf-8",
    )
    published = tmp_path / "published"
    partial = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(published),
            "--processes-file",
            str(processes_file),
            "--target-process",
            "pgp-key-lookup",
        ],
    )
    assert partial.exit_code != 0
    assert (published / "scope.json").exists()

    output = tmp_path / "business-context"
    result = CliRunner().invoke(
        app,
        ["build-business-context", "--input", str(published), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    context = json.loads((output / "context.json").read_text(encoding="utf-8"))
    assert context["context_kind"] == "PROCESS"
    assert context["status"] == "PARTIAL"
    assert "BUSINESS_CONTEXT_PARTIAL_SCOPE" in context["status_reasons"]
    assert context["approved_metadata"]["process"]["description"] == (
        "Looks up configured PGP key material."
    )
    assert any(
        item["code"] == "SCOPE_PROCESS_ENTRYPOINT_UNRESOLVED"
        for item in context["limitations"]
    )


def test_business_context_requires_focused_scope(tmp_path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "build-business-context",
            "--input",
            str(tmp_path),
            "--output",
            str(tmp_path / "business-context"),
        ],
    )

    assert result.exit_code != 0
    assert "BUSINESS_CONTEXT_INPUT_MISSING" in result.output
    assert not (tmp_path / "business-context" / "context.json").exists()


def test_business_context_cli_rejects_input_mode_conflicts(tmp_path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "build-business-context",
            "--input",
            str(tmp_path),
            "--analysis",
            str(tmp_path / "analysis.json"),
            "--output",
            str(tmp_path / "business-context"),
        ],
    )

    assert result.exit_code == 2
    assert "BUSINESS_CONTEXT_INPUT_INVALID" in result.output


def test_business_context_rejects_scope_analysis_reference_mismatch(tmp_path) -> None:
    published = tmp_path / "published"
    _run_analyze(
        [
            "analyze",
            str(_samples()),
            "--output",
            str(published),
            "--target-service",
            "pgp.services.common:readConfig",
            "--dependency-depth",
            "0",
        ]
    )
    bad_scope = tmp_path / "bad-scope.json"
    scope = json.loads((published / "scope.json").read_text(encoding="utf-8"))
    scope["service_memberships"][0]["service"] = "missing.services:target"
    bad_scope.write_text(json.dumps(scope, indent=2, sort_keys=True), encoding="utf-8")

    result = CliRunner().invoke(
        app,
        [
            "build-business-context",
            "--analysis",
            str(published / "analysis.json"),
            "--scope",
            str(bad_scope),
            "--output",
            str(tmp_path / "business-context"),
        ],
    )

    assert result.exit_code != 0
    assert "BUSINESS_CONTEXT_REFERENCE_MISSING" in result.output
    assert not (tmp_path / "business-context" / "context.json").exists()


def test_business_context_rejects_boundary_source_mismatch_and_preserves_bundle(tmp_path) -> None:
    published = _published_service_scope(tmp_path)
    output = tmp_path / "business-context"
    good = CliRunner().invoke(
        app,
        ["build-business-context", "--input", str(published), "--output", str(output)],
    )
    assert good.exit_code == 0, good.output
    old_json = (output / "context.json").read_bytes()
    old_markdown = (output / "context.md").read_bytes()

    bad_scope = tmp_path / "bad-boundary-scope.json"
    scope = _read_json(published / "scope.json")
    assert scope["boundaries"]
    scope["boundaries"][0]["source_service"] = "missing.services:target"
    _write_json(bad_scope, scope)

    result = CliRunner().invoke(
        app,
        [
            "build-business-context",
            "--analysis",
            str(published / "analysis.json"),
            "--scope",
            str(bad_scope),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code != 0
    assert "BUSINESS_CONTEXT_SCOPE_MISMATCH" in result.output
    assert "Traceback" not in result.output
    assert (output / "context.json").read_bytes() == old_json
    assert (output / "context.md").read_bytes() == old_markdown


def test_business_context_rejects_dependency_semantic_mismatches(tmp_path) -> None:
    published = _published_service_scope(tmp_path)
    base_scope = _read_json(published / "scope.json")
    assert base_scope["dependencies"]

    mutations = [
        ("target", lambda edge: edge.__setitem__("target_service", "missing.services:target")),
        (
            "kind",
            lambda edge: edge.__setitem__(
                "dependency_kind",
                "USES_TRANSFORMER"
                if edge["dependency_kind"] != "USES_TRANSFORMER"
                else "INVOKES",
            ),
        ),
    ]
    for label, mutate in mutations:
        scope = json.loads(json.dumps(base_scope))
        mutate(scope["dependencies"][0])
        bad_scope = tmp_path / f"bad-dependency-{label}.json"
        _write_json(bad_scope, scope)
        result = CliRunner().invoke(
            app,
            [
                "build-business-context",
                "--analysis",
                str(published / "analysis.json"),
                "--scope",
                str(bad_scope),
                "--output",
                str(tmp_path / f"context-{label}"),
            ],
        )
        assert result.exit_code != 0
        assert "BUSINESS_CONTEXT_SCOPE_MISMATCH" in result.output
        assert "Traceback" not in result.output
        assert not (tmp_path / f"context-{label}" / "context.json").exists()


def test_business_context_rejects_document_dependency_mismatch(tmp_path) -> None:
    published = _published_service_scope(tmp_path)
    scope = _read_json(published / "scope.json")
    assert scope["document_dependencies"]
    scope["document_dependencies"][0]["target_document"] = "missing.docs:Missing"
    bad_scope = tmp_path / "bad-document-scope.json"
    _write_json(bad_scope, scope)

    result = CliRunner().invoke(
        app,
        [
            "build-business-context",
            "--analysis",
            str(published / "analysis.json"),
            "--scope",
            str(bad_scope),
            "--output",
            str(tmp_path / "business-context"),
        ],
    )

    assert result.exit_code != 0
    assert "BUSINESS_CONTEXT_SCOPE_MISMATCH" in result.output


def test_business_context_rejects_process_projection_and_document_boundary_mismatches(
    tmp_path,
) -> None:
    published = _published_oa_process_scope(tmp_path)

    scope = _read_json(published / "scope.json")
    assert scope["process_projections"]
    scope["process_projections"][0]["process_name"] = "Wrong process"
    bad_process_scope = tmp_path / "bad-process-scope.json"
    _write_json(bad_process_scope, scope)
    result = CliRunner().invoke(
        app,
        [
            "build-business-context",
            "--analysis",
            str(published / "analysis.json"),
            "--scope",
            str(bad_process_scope),
            "--output",
            str(tmp_path / "process-context"),
        ],
    )
    assert result.exit_code != 0
    assert "BUSINESS_CONTEXT_SCOPE_MISMATCH" in result.output

    scope = _read_json(published / "scope.json")
    assert scope["document_boundaries"]
    scope["document_boundaries"][0]["source"] = "missing.docs:Missing"
    bad_document_scope = tmp_path / "bad-process-document-scope.json"
    _write_json(bad_document_scope, scope)
    result = CliRunner().invoke(
        app,
        [
            "build-business-context",
            "--analysis",
            str(published / "analysis.json"),
            "--scope",
            str(bad_document_scope),
            "--output",
            str(tmp_path / "document-context"),
        ],
    )
    assert result.exit_code != 0
    assert "BUSINESS_CONTEXT_SCOPE_MISMATCH" in result.output


def test_business_context_allows_unrelated_duplicate_service_identities(tmp_path) -> None:
    packages_root = tmp_path / "packages"
    for package in ("DupA", "DupB"):
        duplicate = packages_root / package / "ns" / "dup" / "services" / "target"
        duplicate.mkdir(parents=True)
        _write_node(duplicate / "node.ndf")
        (duplicate / "flow.xml").write_text(
            '<FLOW VERSION="3.0" CLEANUP="true" />',
            encoding="utf-8",
        )
    unique = packages_root / "Unique" / "ns" / "unique" / "services" / "root"
    unique.mkdir(parents=True)
    _write_node(unique / "node.ndf")
    (unique / "flow.xml").write_text(
        '<FLOW VERSION="3.0" CLEANUP="true" />',
        encoding="utf-8",
    )
    published = tmp_path / "published"
    _run_analyze(
        [
            "analyze",
            str(packages_root),
            "--output",
            str(published),
            "--target-service",
            "unique.services:root",
        ]
    )

    result = CliRunner().invoke(
        app,
        [
            "build-business-context",
            "--input",
            str(published),
            "--output",
            str(tmp_path / "business-context"),
        ],
    )

    assert result.exit_code == 0, result.output
    context = json.loads(
        (tmp_path / "business-context" / "context.json").read_text(encoding="utf-8")
    )
    assert context["subject"]["service"] == "unique.services:root"


def test_business_context_withholds_map_literal_values(tmp_path) -> None:
    package_root = tmp_path / "packages"
    service_dir = package_root / "Pkg" / "ns" / "foo" / "bar"
    service_dir.mkdir(parents=True)
    _write_node(service_dir / "node.ndf")
    _write_flow_with_mapset(service_dir / "flow.xml", "/target;1;0", "visible-value")
    config = tmp_path / "config.yml"
    config.write_text("extraction:\n  literals:\n    mode: include\n", encoding="utf-8")
    published = tmp_path / "published"
    _run_analyze(
        [
            "analyze",
            str(package_root),
            "--config",
            str(config),
            "--output",
            str(published),
            "--target-service",
            "foo:bar",
        ]
    )
    assert "visible-value" in (published / "analysis.json").read_text(encoding="utf-8")

    output = tmp_path / "business-context"
    result = CliRunner().invoke(
        app,
        ["build-business-context", "--input", str(published), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    context_text = (output / "context.json").read_text(encoding="utf-8")
    context = json.loads(context_text)
    assert "visible-value" not in context_text
    assert context["mappings"][0]["literal_assignment"] is True
    assert context["mappings"][0]["literal_value"] == "<withheld>"


def test_business_context_publication_rolls_back_mixed_bundle_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service_context = _build_context(_published_service_scope(tmp_path))
    package_published = tmp_path / "package-published"
    _run_analyze(
        [
            "analyze",
            str(_samples()),
            "--output",
            str(package_published),
            "--target-package",
            "PGP",
            "--dependency-depth",
            "0",
        ]
    )
    package_context = _build_context(package_published)
    output = tmp_path / "business-context"
    write_business_context_outputs(output, service_context)
    old_json = (output / "context.json").read_bytes()
    old_markdown = (output / "context.md").read_bytes()

    original_replace = Path.replace

    def fail_markdown_publish(self: Path, target: Path) -> Path:
        if self.name == ".context.md.tmp":
            raise OSError("simulated second-file publish failure")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_markdown_publish)
    with pytest.raises(BusinessContextError) as error:
        write_business_context_outputs(output, package_context)

    assert error.value.code == BusinessContextErrorCode.OUTPUT_FAILED
    assert (output / "context.json").read_bytes() == old_json
    assert (output / "context.md").read_bytes() == old_markdown
    assert not list(output.glob(".*.tmp"))
    assert not list(output.glob(".*.bak"))


def test_business_context_first_build_failure_leaves_no_partial_bundle(tmp_path) -> None:
    published = _published_service_scope(tmp_path)
    output = tmp_path / "business-context"
    output.mkdir()
    (output / "context.md").mkdir()

    result = CliRunner().invoke(
        app,
        ["build-business-context", "--input", str(published), "--output", str(output)],
    )

    assert result.exit_code != 0
    assert "BUSINESS_CONTEXT_OUTPUT_FAILED" in result.output
    assert not (output / "context.json").exists()


def test_business_context_records_upstream_disclosure_redaction(tmp_path) -> None:
    package_root = tmp_path / "packages"
    service_dir = package_root / "Pkg" / "ns" / "foo" / "root"
    service_dir.mkdir(parents=True)
    _write_node(service_dir / "node.ndf")
    (service_dir / "flow.xml").write_text(
        '<FLOW VERSION="3.0" CLEANUP="true" />',
        encoding="utf-8",
    )
    processes_file = tmp_path / "processes.yml"
    processes_file.write_text(
        """version: 1
processes:
  - id: redaction-test
    name: Redaction test
    description: "Contains password=super-secret-marker"
    entrypoints:
      - foo:root
""",
        encoding="utf-8",
    )
    published = tmp_path / "published"
    _run_analyze(
        [
            "analyze",
            str(package_root),
            "--output",
            str(published),
            "--processes-file",
            str(processes_file),
            "--target-process",
            "redaction-test",
        ]
    )
    output = tmp_path / "business-context"

    result = CliRunner().invoke(
        app,
        ["build-business-context", "--input", str(published), "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    context_text = (output / "context.json").read_text(encoding="utf-8")
    context = json.loads(context_text)
    assert "super-secret-marker" not in context_text
    assert context["approved_metadata"]["process"]["description"] == (
        "<redacted:secret-free-text>"
    )
    assert context["status"] == "COMPLETE"
    assert context["status_reasons"].count("BUSINESS_CONTEXT_DISCLOSURE_REDACTED") == 1
    assert any(
        item["code"] == "BUSINESS_CONTEXT_DISCLOSURE_REDACTED"
        for item in context["limitations"]
    )


def test_business_context_active_evidence_types_have_emission_paths(tmp_path) -> None:
    service_context = _context_json(
        _published_service_scope(tmp_path),
        tmp_path / "service-context",
    )
    process_context = _context_json(
        _published_oa_process_scope(tmp_path),
        tmp_path / "process-context",
    )
    emitted = {
        item["evidence_type"]
        for context in (service_context, process_context)
        for item in context["evidence"]
    }
    assert emitted == {item.value for item in BusinessEvidenceType}


def _run_analyze(args: list[str]) -> None:
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output


def _assert_evidence_references_resolve(context: dict[str, Any]) -> None:
    evidence_ids = {item["evidence_id"] for item in context["evidence"]}
    referenced: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                if key == "evidence_ids":
                    referenced.update(nested)
                else:
                    visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(context)
    assert referenced <= evidence_ids


def _samples() -> Path:
    return Path(__file__).resolve().parents[2] / "samples"


def _published_service_scope(tmp_path: Path) -> Path:
    published = tmp_path / "published-service"
    _run_analyze(
        [
            "analyze",
            str(_samples()),
            "--output",
            str(published),
            "--target-service",
            "pgp.services.common:readConfig",
            "--dependency-depth",
            "1",
        ]
    )
    return published


def _published_oa_process_scope(tmp_path: Path) -> Path:
    processes_file = tmp_path / "processes.yml"
    processes_file.write_text(
        """version: 1
processes:
  - id: oa-address-validation
    name: OA address validation
    entrypoints:
      - oa.adapter.geographicAddressManagement:createGeographicAddressValidation
""",
        encoding="utf-8",
    )
    published = tmp_path / "published-process"
    _run_analyze(
        [
            "analyze",
            str(_samples()),
            "--output",
            str(published),
            "--processes-file",
            str(processes_file),
            "--target-process",
            "oa-address-validation",
            "--dependency-depth",
            "1",
        ]
    )
    return published


def _build_context(published: Path):
    inputs = load_business_context_inputs(
        published / "analysis.json",
        published / "scope.json",
    )
    return build_business_context(inputs).context


def _context_json(published: Path, output: Path) -> dict[str, Any]:
    result = CliRunner().invoke(
        app,
        ["build-business-context", "--input", str(published), "--output", str(output)],
    )
    assert result.exit_code == 0, result.output
    return _read_json(output / "context.json")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_node(path: Path) -> None:
    path.write_text(
        """<Values version="2.0">
  <value name="svc_type">flow</value>
  <record name="svc_sig">
    <record name="sig_in"><array name="rec_fields" type="record" depth="1" /></record>
    <record name="sig_out"><array name="rec_fields" type="record" depth="1" /></record>
  </record>
</Values>""",
        encoding="utf-8",
    )


def _write_flow_with_mapset(path: Path, field: str, value: str) -> None:
    path.write_text(
        f"""<FLOW VERSION="3.0" CLEANUP="true">
<MAP MODE="STANDALONE">
  <MAPSET FIELD="{field}">
    <DATA ENCODING="XMLValues" I18N="true">
      <Values version="2.0">
        <value name="xml">{value}</value>
        <record name="type">
          <value name="field_name">{field.strip('/').split(';', 1)[0]}</value>
          <value name="field_type">string</value>
        </record>
      </Values>
    </DATA>
  </MAPSET>
</MAP>
</FLOW>""",
        encoding="utf-8",
    )
