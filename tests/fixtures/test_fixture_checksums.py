from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path

MANIFEST = Path(__file__).with_name("checksums.sha256")
FIXTURE_ROOTS = ("samples/OriginalSmall", "samples/PGP")
CHECKSUM_LINE = re.compile(r"^[0-9a-f]{64}  samples/(?:OriginalSmall|PGP)/.+$")


def test_fixture_checksum_manifest_matches_samples() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    entries = _read_manifest()
    manifest_paths = [path for _, path in entries]
    actual_paths = _fixture_paths(repo_root)

    assert manifest_paths == sorted(manifest_paths)
    assert manifest_paths == actual_paths

    mismatches = [
        path
        for expected_hash, path in entries
        if sha256((repo_root / path).read_bytes()).hexdigest() != expected_hash
    ]
    assert mismatches == []


def _read_manifest() -> list[tuple[str, str]]:
    lines = MANIFEST.read_text(encoding="utf-8").splitlines()
    assert lines
    assert all(CHECKSUM_LINE.fullmatch(line) for line in lines)

    entries: list[tuple[str, str]] = []
    for line in lines:
        digest, path = line.split("  ", 1)
        assert "\\" not in path
        assert ":" not in path
        assert not Path(path).is_absolute()
        entries.append((digest, path))
    return entries


def _fixture_paths(repo_root: Path) -> list[str]:
    paths: list[str] = []
    for fixture_root in FIXTURE_ROOTS:
        paths.extend(
            path.relative_to(repo_root).as_posix()
            for path in (repo_root / fixture_root).rglob("*")
            if path.is_file()
        )
    return sorted(paths)
