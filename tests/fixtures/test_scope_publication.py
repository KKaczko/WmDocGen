from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from wm_doc.cli import app
from wm_doc.render.service_markdown import service_markdown_filename
from wm_doc.scope_analysis import ScopeBoundaryStatus, _add_boundary

MARKDOWN_LINK_RE = re.compile(r"(!?)\[[^\]]*\]\(([^)]+)\)")
URL_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def test_focused_service_scope_publishes_subset_and_full_analysis(tmp_path) -> None:
    output = tmp_path / "service-scope"

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(output),
            "--target-service",
            "pgp.services.common:readConfig",
            "--dependency-depth",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Full snapshot technical metrics:" in result.output
    assert "Focused publication metrics:" in result.output
    assert "- selector type: SERVICE" in result.output
    analysis_payload = json.loads((output / "analysis.json").read_text(encoding="utf-8"))
    scope_payload = json.loads((output / "scope.json").read_text(encoding="utf-8"))

    assert analysis_payload["schema_version"] == "analysis.v8"
    assert len(
        [
            service
            for package in analysis_payload["packages"]
            for service in package["services"]
        ]
    ) == 35
    assert scope_payload["schema_version"] == "scope.v1"
    assert scope_payload["selector"]["selector_type"] == "SERVICE"
    assert scope_payload["metrics"]["services_included"] == 2
    assert scope_payload["root_services"] == ["pgp.services.common:readConfig"]
    assert (output / "scope.md").exists()
    assert "analysis.json` describes the complete discovered snapshot" in (
        output / "index.md"
    ).read_text(encoding="utf-8")
    assert not (output / "graphs" / "dependencies.dot").exists()
    assert not (output / "graphs" / "documents.dot").exists()
    assert (output / "graphs" / "scope.dot").exists()
    assert (output / "graphs" / "scope-documents.dot").exists()
    assert {
        path.name for path in (output / "services").glob("*.md")
    } == {
        service_markdown_filename("pgp.services.common:readConfig"),
        service_markdown_filename("pgp.services.common:selectFromConfig"),
    }
    _assert_generated_markdown_links_valid(output)


def test_no_selector_remains_global_m7_output_shape(tmp_path) -> None:
    output = tmp_path / "full"

    result = CliRunner().invoke(app, ["analyze", str(_samples()), "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert not (output / "scope.json").exists()
    assert not (output / "scope.md").exists()
    assert (output / "graphs" / "dependencies.dot").exists()
    assert (output / "graphs" / "documents.dot").exists()
    assert not (output / "graphs" / "scope.dot").exists()
    assert sum(1 for path in output.rglob("*") if path.is_file()) == 48


def test_scope_selector_validation_rejects_conflicts_and_repetition(tmp_path) -> None:
    conflict_output = tmp_path / "conflict"
    conflict = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(conflict_output),
            "--target-service",
            "pgp.services.common:readConfig",
            "--target-package",
            "PGP",
        ],
    )
    assert conflict.exit_code != 0
    assert "SCOPE_SELECTOR_CONFLICT" in conflict.output
    assert not conflict_output.exists()

    repeated_output = tmp_path / "repeated"
    repeated = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(repeated_output),
            "--target-service",
            "pgp.services.common:readConfig",
            "--target-service",
            "pgp.services.common:selectFromConfig",
        ],
    )
    assert repeated.exit_code != 0
    assert "SCOPE_SELECTOR_CONFLICT" in repeated.output
    assert not repeated_output.exists()

    depth_without_selector_output = tmp_path / "depth-without-selector"
    depth_without_selector = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(depth_without_selector_output),
            "--dependency-depth",
            "1",
        ],
    )
    assert depth_without_selector.exit_code != 0
    assert "SCOPE_SELECTOR_CONFLICT" in depth_without_selector.output
    assert not depth_without_selector_output.exists()


def test_namespace_selector_uses_segment_boundary_matching(tmp_path) -> None:
    miss_output = tmp_path / "namespace-miss"
    miss = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(miss_output),
            "--target-namespace",
            "pgp.service",
        ],
    )
    assert miss.exit_code != 0
    assert "Target namespace was not found" in miss.output
    assert not miss_output.exists()

    output = tmp_path / "namespace-hit"
    hit = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(output),
            "--target-namespace",
            "pgp.services.common",
            "--dependency-depth",
            "0",
        ],
    )
    assert hit.exit_code == 0, hit.output
    scope = json.loads((output / "scope.json").read_text(encoding="utf-8"))
    assert scope["selector"]["selector_type"] == "NAMESPACE"
    assert scope["metrics"]["roots_resolved"] == 5
    assert scope["metrics"]["services_by_minimum_depth"] == {"0": 5}
    assert all(
        service.startswith("pgp.services.common:")
        for service in scope["root_services"]
    )
    _assert_generated_markdown_links_valid(output)


def test_process_scope_projects_depth_and_generates_only_selected_process(tmp_path) -> None:
    processes_file = tmp_path / "processes.yml"
    processes_file.write_text(
        """version: 1
processes:
  - id: pgp-key-lookup
    name: PGP key lookup
    entrypoints:
      - pgp.services.registry:getPubKey
      - pgp.services.registry:getSecKey
""",
        encoding="utf-8",
    )
    output = tmp_path / "process-scope"

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(output),
            "--processes-file",
            str(processes_file),
            "--target-process",
            "pgp-key-lookup",
            "--dependency-depth",
            "1",
        ],
    )

    assert result.exit_code == 0, result.output
    scope = json.loads((output / "scope.json").read_text(encoding="utf-8"))
    projection = scope["process_projections"][0]
    assert projection["process_id"] == "pgp-key-lookup"
    assert projection["full_member_count"] > projection["published_member_count"]
    assert projection["boundary_dependency_count"] >= 1
    assert (output / "processes" / "index.md").exists()
    assert (output / "processes" / "pgp-key-lookup.md").exists()
    assert (output / "graphs" / "processes" / "pgp-key-lookup.dot").exists()
    assert not (output / "graphs" / "dependencies.dot").exists()
    process_page = (output / "processes" / "pgp-key-lookup.md").read_text(
        encoding="utf-8"
    )
    assert "Full discovered process members" in process_page
    assert "Published process members" in process_page
    _assert_generated_markdown_links_valid(output)


def test_selected_duplicate_process_id_is_fatal_ambiguous(tmp_path) -> None:
    processes_file = tmp_path / "processes.yml"
    processes_file.write_text(
        """version: 1
processes:
  - id: duplicate-process
    name: First duplicate process
    entrypoints:
      - pgp.services.registry:getPubKey
  - id: duplicate-process
    name: Second duplicate process
    entrypoints:
      - pgp.services.registry:getSecKey
""",
        encoding="utf-8",
    )
    output = tmp_path / "duplicate-process-scope"

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(output),
            "--processes-file",
            str(processes_file),
            "--target-process",
            "duplicate-process",
        ],
    )

    assert result.exit_code != 0
    assert "SCOPE_TARGET_AMBIGUOUS" in result.output
    assert "Traceback" not in result.output
    assert not (output / "scope.json").exists()
    assert not (output / "scope.md").exists()
    assert not (output / "services").exists()
    assert not (output / "processes").exists()


def test_unrelated_duplicate_process_id_does_not_block_unique_process(tmp_path) -> None:
    processes_file = tmp_path / "processes.yml"
    processes_file.write_text(
        """version: 1
processes:
  - id: duplicate-process
    name: First duplicate process
    entrypoints:
      - pgp.services.registry:getPubKey
  - id: duplicate-process
    name: Second duplicate process
    entrypoints:
      - pgp.services.registry:getSecKey
  - id: pgp-key-lookup
    name: PGP key lookup
    entrypoints:
      - pgp.services.registry:getPubKey
      - pgp.services.registry:getSecKey
""",
        encoding="utf-8",
    )
    output = tmp_path / "unique-process-scope"

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(output),
            "--processes-file",
            str(processes_file),
            "--target-process",
            "pgp-key-lookup",
        ],
    )

    assert result.exit_code == 0, result.output
    scope = json.loads((output / "scope.json").read_text(encoding="utf-8"))
    assert scope["selector"]["selector_type"] == "PROCESS"
    assert scope["selector"]["value"] == "pgp-key-lookup"


def test_fatal_scope_resolution_cli_diagnostics_include_codes(tmp_path) -> None:
    unknown_service_output = tmp_path / "unknown-service"
    unknown_service = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(unknown_service_output),
            "--target-service",
            "pgp.services.common:missingService",
        ],
    )
    assert unknown_service.exit_code != 0
    assert "SCOPE_TARGET_NOT_FOUND" in unknown_service.output
    assert "Traceback" not in unknown_service.output
    assert not unknown_service_output.exists()

    processes_file = tmp_path / "processes.yml"
    processes_file.write_text(
        """version: 1
processes:
  - id: pgp-key-lookup
    name: PGP key lookup
    entrypoints:
      - pgp.services.registry:getPubKey
""",
        encoding="utf-8",
    )
    unknown_process_output = tmp_path / "unknown-process"
    unknown_process = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(unknown_process_output),
            "--processes-file",
            str(processes_file),
            "--target-process",
            "missing-process",
        ],
    )
    assert unknown_process.exit_code != 0
    assert "SCOPE_TARGET_NOT_FOUND" in unknown_process.output
    assert "Traceback" not in unknown_process.output
    assert not unknown_process_output.exists()

    missing_catalog_output = tmp_path / "missing-catalog"
    missing_catalog = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(missing_catalog_output),
            "--target-process",
            "pgp-key-lookup",
        ],
    )
    assert missing_catalog.exit_code != 0
    assert "SCOPE_PROCESS_CONFIG_REQUIRED" in missing_catalog.output
    assert "Traceback" not in missing_catalog.output
    assert not missing_catalog_output.exists()


def test_duplicate_service_identity_cli_diagnostic_includes_ambiguity_code(tmp_path) -> None:
    packages_root = tmp_path / "packages"
    for package in ("DupA", "DupB"):
        _write_minimal_flow_service(
            packages_root / package / "ns" / "dup" / "services" / "target"
        )
    output = tmp_path / "duplicate-service-scope"

    result = CliRunner().invoke(
        app,
        [
            "analyze",
            str(packages_root),
            "--output",
            str(output),
            "--target-service",
            "dup.services:target",
        ],
    )

    assert result.exit_code != 0
    assert "SCOPE_TARGET_AMBIGUOUS" in result.output
    assert "Traceback" not in result.output
    assert not output.exists()


def test_scope_boundary_identity_includes_target_category() -> None:
    grouped = {}

    _add_boundary(
        grouped,
        "pkg.services:caller",
        "<shared-target>",
        "dependency_target",
        "INVOKES",
        ScopeBoundaryStatus.UNRESOLVED,
        1,
        ["dependency-a"],
        [],
    )
    _add_boundary(
        grouped,
        "pkg.services:caller",
        "<shared-target>",
        "finding_target",
        "INVOKES",
        ScopeBoundaryStatus.UNRESOLVED,
        1,
        ["finding-a"],
        [],
    )

    boundaries = [
        accumulator.to_boundary()
        for _, accumulator in sorted(grouped.items(), key=lambda item: item[0])
    ]
    assert len(boundaries) == 2
    assert {boundary.target_category for boundary in boundaries} == {
        "dependency_target",
        "finding_target",
    }
    assert len({boundary.id for boundary in boundaries}) == 2
    assert [boundary.occurrence_count for boundary in boundaries] == [1, 1]


def test_scope_output_is_deterministic(tmp_path) -> None:
    outputs = [tmp_path / "first", tmp_path / "second"]
    for output in outputs:
        result = CliRunner().invoke(
            app,
            [
                "analyze",
                str(_samples()),
                "--output",
                str(output),
                "--target-package",
                "PGP",
                "--dependency-depth",
                "1",
            ],
        )
        assert result.exit_code == 0, result.output

    comparable = [
        "scope.json",
        "scope.md",
        "index.md",
        "entrypoints.md",
        "graphs/index.md",
        "graphs/scope.dot",
    ]
    for relative in comparable:
        assert (outputs[0] / relative).read_bytes() == (outputs[1] / relative).read_bytes()


def test_scoped_to_full_output_removes_stale_scope_files(tmp_path) -> None:
    output = tmp_path / "transition"
    scoped = CliRunner().invoke(
        app,
        [
            "analyze",
            str(_samples()),
            "--output",
            str(output),
            "--target-service",
            "pgp.services.common:readConfig",
        ],
    )
    assert scoped.exit_code == 0, scoped.output
    assert (output / "scope.json").exists()
    assert (output / "graphs" / "scope.dot").exists()

    full = CliRunner().invoke(app, ["analyze", str(_samples()), "--output", str(output)])

    assert full.exit_code == 0, full.output
    assert not (output / "scope.json").exists()
    assert not (output / "scope.md").exists()
    assert not (output / "graphs" / "scope.dot").exists()
    assert (output / "graphs" / "dependencies.dot").exists()
    assert (output / "graphs" / "documents.dot").exists()


def _assert_generated_markdown_links_valid(output_root: Path) -> None:
    root = output_root.resolve()
    for markdown_path in sorted(root.rglob("*.md")):
        text = markdown_path.read_text(encoding="utf-8")
        for raw_target, is_image in _iter_generated_markdown_links(text):
            target = raw_target.strip()
            if not target:
                continue
            if WINDOWS_ABSOLUTE_RE.match(target) or Path(target).is_absolute():
                raise AssertionError(f"{markdown_path} contains absolute link {target!r}")
            if URL_SCHEME_RE.match(target):
                if is_image:
                    raise AssertionError(
                        f"{markdown_path} contains external image link {target!r}"
                    )
                continue
            path_part = target.split("#", 1)[0]
            if not path_part:
                continue
            resolved = (markdown_path.parent / path_part).resolve()
            try:
                resolved.relative_to(root)
            except ValueError as exc:
                raise AssertionError(
                    f"{markdown_path} contains link escaping output root: {target!r}"
                ) from exc
            assert resolved.exists(), f"{markdown_path} links to missing target {target!r}"


def _iter_generated_markdown_links(text: str) -> list[tuple[str, bool]]:
    links: list[tuple[str, bool]] = []
    in_fence = False
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        links.extend(
            (match.group(2), bool(match.group(1))) for match in MARKDOWN_LINK_RE.finditer(line)
        )
    return links


def _samples() -> Path:
    return Path(__file__).resolve().parents[2] / "samples"


def _write_minimal_flow_service(service_dir: Path) -> None:
    service_dir.mkdir(parents=True, exist_ok=True)
    (service_dir / "node.ndf").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<Values version="2.0">
  <value name="svc_type">flow</value>
  <record name="svc_sig" javaclass="com.wm.util.Values">
    <record name="sig_in" javaclass="com.wm.util.Values">
      <array name="rec_fields" type="record" depth="1" />
    </record>
    <record name="sig_out" javaclass="com.wm.util.Values">
      <array name="rec_fields" type="record" depth="1" />
    </record>
  </record>
</Values>
""",
        encoding="utf-8",
    )
    (service_dir / "flow.xml").write_text(
        '<FLOW VERSION="3.0" CLEANUP="true" />',
        encoding="utf-8",
    )
