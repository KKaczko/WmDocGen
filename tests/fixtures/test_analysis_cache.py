"""Faster re-runs: the analysis of unchanged packages is reused."""

from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from wm_doc.analysis_cache import analyze_cached
from wm_doc.cli import app
from wm_doc.config import PackageSelectionConfig, load_config
from wm_doc.render.analysis_json import render_analysis_json

SAMPLES = Path(__file__).resolve().parents[2] / "samples"
READ_CONFIG_FLOW = Path("PGP/ns/pgp/services/common/readConfig/flow.xml")


def _copy_samples(tmp_path: Path) -> Path:
    root = tmp_path / "packages"
    shutil.copytree(SAMPLES, root)
    return root


def test_second_run_reuses_an_identical_analysis(tmp_path: Path) -> None:
    root = _copy_samples(tmp_path)
    cache = tmp_path / "cache"

    first, first_reused = analyze_cached(root, load_config(None), cache_dir=cache)
    second, second_reused = analyze_cached(root, load_config(None), cache_dir=cache)

    assert (first_reused, second_reused) == (False, True)
    assert render_analysis_json(second) == render_analysis_json(first)
    assert second.unique_dependencies == first.unique_dependencies
    assert len(list(cache.glob("*.jsonl.gz"))) == 1


def test_changed_file_triggers_a_fresh_analysis_and_replaces_the_entry(tmp_path: Path) -> None:
    root = _copy_samples(tmp_path)
    cache = tmp_path / "cache"
    analyze_cached(root, load_config(None), cache_dir=cache)
    flow = root / READ_CONFIG_FLOW
    flow.write_text(
        flow.read_text(encoding="utf-8").replace("pub.io:close", "pub.io:streamToBytes"),
        encoding="utf-8",
    )

    analysis, reused = analyze_cached(root, load_config(None), cache_dir=cache)

    assert not reused
    targets = {
        call.target
        for call in analysis.call_occurrences
        if call.caller == "pgp.services.common:readConfig"
    }
    assert "pub.io:streamToBytes" in targets
    assert len(list(cache.glob("*.jsonl.gz"))) == 1


def test_different_configuration_is_not_reused(tmp_path: Path) -> None:
    root = _copy_samples(tmp_path)
    cache = tmp_path / "cache"
    analyze_cached(root, load_config(None), cache_dir=cache)
    only_pgp = load_config(None).model_copy(
        update={"packages": PackageSelectionConfig(include=["PGP"])}
    )

    analysis, reused = analyze_cached(root, only_pgp, cache_dir=cache)

    assert not reused
    assert [package.name for package in analysis.packages] == ["PGP"]


def test_damaged_cache_entry_is_rebuilt(tmp_path: Path) -> None:
    root = _copy_samples(tmp_path)
    cache = tmp_path / "cache"
    analyze_cached(root, load_config(None), cache_dir=cache)
    entry = next(cache.glob("*.jsonl.gz"))
    entry.write_bytes(b"not gzip")

    analysis, reused = analyze_cached(root, load_config(None), cache_dir=cache)

    assert not reused
    assert len(analysis.services) == 35


def test_cli_reports_reuse_and_can_skip_the_cache(tmp_path: Path) -> None:
    root = _copy_samples(tmp_path)
    runner = CliRunner()

    first = runner.invoke(app, ["stats", str(root)])
    second = runner.invoke(app, ["stats", str(root)])
    fresh = runner.invoke(app, ["stats", str(root), "--no-analysis-cache"])

    assert first.exit_code == second.exit_code == fresh.exit_code == 0
    assert "Reused the cached analysis" not in first.output
    assert "Reused the cached analysis" in second.output
    assert "Reused the cached analysis" not in fresh.output


def test_truncated_cache_entry_is_rebuilt(tmp_path: Path) -> None:
    import gzip

    root = _copy_samples(tmp_path)
    cache = tmp_path / "cache"
    analyze_cached(root, load_config(None), cache_dir=cache)
    entry = next(cache.glob("*.jsonl.gz"))
    lines = gzip.decompress(entry.read_bytes()).decode("utf-8").splitlines(keepends=True)
    entry.write_bytes(gzip.compress("".join(lines[:-1]).encode("utf-8")))

    analysis, reused = analyze_cached(root, load_config(None), cache_dir=cache)

    assert not reused
    assert len(analysis.packages) == len(lines) - 2


def test_entry_of_the_earlier_format_is_replaced(tmp_path: Path) -> None:
    root = _copy_samples(tmp_path)
    cache = tmp_path / "cache"
    analyze_cached(root, load_config(None), cache_dir=cache)
    entry = next(cache.glob("*.jsonl.gz"))
    old_entry = entry.with_name(entry.name.split("-")[0] + "-0123.json.gz")
    old_entry.write_bytes(b"old format")
    entry.unlink()

    analyze_cached(root, load_config(None), cache_dir=cache)

    assert not old_entry.exists()
    assert len(list(cache.glob("*.jsonl.gz"))) == 1
