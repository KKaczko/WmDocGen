"""No command writes into the analysed packages folder or cleans an output folder around it.

`analyze --output .` next to a `packages` folder used to delete it: the output cleanup removes
a managed `packages/` page folder. Every command that writes files now checks its paths first.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from flowxml import FlowPackage, invoke
from typer.testing import CliRunner

from wm_doc.cli import app
from wm_doc.output_cleanup import OutputLocationError, check_outside_packages


def _packages(root: Path) -> Path:
    packages = root / "packages"
    FlowPackage(packages, "Orders").service("orders.api:route", invoke("orders.api:helper"))
    return packages


def _files(folder: Path) -> list[str]:
    return sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*"))


@pytest.mark.parametrize("focused", [[], ["--target-service", "orders.api:route"]])
def test_analyze_refuses_an_output_folder_that_contains_the_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, focused: list[str]
) -> None:
    packages = _packages(tmp_path)
    before = _files(packages)
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["analyze", "packages", "--output", ".", *focused])

    assert result.exit_code == 2, result.output
    assert "PACKAGES_INSIDE_OUTPUT" in result.output
    assert _files(packages) == before
    assert not (tmp_path / "analysis.json").exists()


@pytest.mark.parametrize("inside", ["", "out", "Orders/out"])
def test_analyze_refuses_an_output_folder_inside_the_packages(tmp_path: Path, inside: str) -> None:
    packages = _packages(tmp_path)
    before = _files(packages)

    result = CliRunner().invoke(app, ["analyze", str(packages), "-o", str(packages / inside)])

    assert result.exit_code == 2, result.output
    assert "OUTPUT_INSIDE_PACKAGES" in result.output
    assert _files(packages) == before


@pytest.mark.parametrize(
    "command",
    [
        ["scan", "{packages}", "-o", "{packages}/inventory"],
        ["stats", "{packages}", "-o", "{packages}/stats.md"],
        ["probe-shapes", "{packages}", "-o", "{packages}/shapes.md"],
        ["status", "{packages}", "--docs-dir", "{packages}/service-docs"],
        ["describe", "{packages}", "--model", "m", "--all", "--docs-dir", "{packages}/docs"],
        [
            "describe",
            "{packages}",
            "--model",
            "m",
            "--all",
            "--docs-dir",
            "{root}/docs",
            "--cache-dir",
            "{packages}/cache",
        ],
        ["overview", "{packages}", "--model", "m", "--all", "--docs-dir", "{packages}/docs"],
        ["explorer", "build", "{packages}", "-o", "{packages}/explorer"],
    ],
    ids=[
        "scan",
        "stats",
        "probe-shapes",
        "status",
        "describe-docs",
        "describe-cache",
        "overview",
        "explorer",
    ],
)
def test_every_writing_command_refuses_a_path_inside_the_packages(
    tmp_path: Path, command: list[str]
) -> None:
    packages = _packages(tmp_path)
    before = _files(packages)
    args = [part.format(packages=packages, root=tmp_path) for part in command]

    result = CliRunner().invoke(app, args)

    assert result.exit_code == 2, result.output
    assert "OUTPUT_INSIDE_PACKAGES" in result.output
    assert _files(packages) == before


def test_a_sibling_folder_with_a_shared_name_prefix_is_allowed(tmp_path: Path) -> None:
    packages = tmp_path / "packages"

    check_outside_packages(tmp_path / "packages-docs", packages, "output folder")
    check_outside_packages(tmp_path / "pack", packages, "output folder")


@pytest.mark.skipif(os.name != "nt", reason="only Windows paths ignore case")
def test_paths_are_compared_without_case_on_windows(tmp_path: Path) -> None:
    packages = _packages(tmp_path)

    with pytest.raises(OutputLocationError) as caught:
        check_outside_packages(Path(str(packages).upper()) / "out", packages, "output folder")

    assert caught.value.code == "OUTPUT_INSIDE_PACKAGES"


def test_a_link_into_the_packages_is_followed(tmp_path: Path) -> None:
    packages = _packages(tmp_path)
    link = tmp_path / "link"
    try:
        link.symlink_to(packages, target_is_directory=True)
    except OSError:
        pytest.skip("this system does not allow symbolic links")

    with pytest.raises(OutputLocationError) as caught:
        check_outside_packages(link / "out", packages, "output folder")

    assert caught.value.code == "OUTPUT_INSIDE_PACKAGES"
