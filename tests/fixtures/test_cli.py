from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from wm_doc.cli import app


def test_scan_cli_writes_inventory_outputs(tmp_path) -> None:
    output = tmp_path / "out"
    samples = Path(__file__).resolve().parents[2] / "samples"
    result = CliRunner().invoke(app, ["scan", str(samples), "--output", str(output)])

    assert result.exit_code == 0, result.output
    assert (output / "inventory.json").exists()
    assert (output / "fixture-inventory.md").exists()
    assert "Scanned 2 package(s)" in result.output
