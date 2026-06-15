from __future__ import annotations

from collections import Counter
from pathlib import Path

from wm_doc.discovery import scan_path
from wm_doc.render.json import render_inventory_json


def test_scan_samples_discovers_expected_artifact_counts() -> None:
    inventory = scan_path(_repo_root() / "samples")

    assert [package.name for package in inventory.packages] == ["OAAdapter", "PGP"]

    artifacts = [artifact for package in inventory.packages for artifact in package.artifacts]
    counts = Counter(artifact.probable_type for artifact in artifacts)

    assert counts["flow_service"] == 24
    assert counts["java_service"] == 11
    assert counts["specification"] == 8
    assert counts["document_type"] == 7
    assert counts["namespace_folder"] == 14
    assert counts["helper_backup_file"] == 23

    pgp = next(package for package in inventory.packages if package.name == "PGP")
    assert pgp.aliases == ["GCS_PGP", "WxPGP"]
    assert any(finding.code == "PGP_PROVENANCE_UNKNOWN" for finding in pgp.findings)


def test_scan_samples_json_is_deterministic() -> None:
    samples = _repo_root() / "samples"

    first = render_inventory_json(scan_path(samples))
    second = render_inventory_json(scan_path(samples))

    assert first == second


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]
