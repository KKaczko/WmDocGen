"""Reuse the last analysis of a packages directory when none of its files changed.

`stats`, `analyze`, `describe`, `status` and `probe-shapes` all start from a full analysis,
which takes minutes for a server with a couple of thousand services but only about a second
to reload. The cache key is a fingerprint of the tool and schema version, the configuration,
the explicit `processes.yml`, and every file under the packages directory (relative path, size,
modification time). Any change to a file therefore triggers a fresh analysis.

One entry is kept per packages directory and configuration, stored as gzip-compressed
`analysis.json` content in the user's cache folder. It holds the same data as `analysis.json`;
a damaged or unreadable entry is ignored and rebuilt.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path

from pydantic import ValidationError

from wm_doc import __version__
from wm_doc.analysis import analyze_path
from wm_doc.config import AppConfig
from wm_doc.ir import ANALYSIS_SCHEMA_VERSION, AnalysisResult

CACHE_FORMAT = "analysis-cache.v1"
CACHE_DIR_ENV = "WM_DOC_ANALYSIS_CACHE_DIR"


def default_analysis_cache_dir() -> Path:
    override = os.environ.get(CACHE_DIR_ENV)
    if override:
        return Path(override)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local_app_data:
        return Path(local_app_data) / "wm-doc" / "analysis-cache"
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache) / "wm-doc" / "analysis-cache"
    return Path.home() / ".cache" / "wm-doc" / "analysis-cache"


def input_fingerprint(
    scan_root: Path,
    config: AppConfig,
    processes_file: Path | None,
    processes_file_explicit: bool,
) -> str:
    digest = hashlib.sha256()
    settings = {
        "format": CACHE_FORMAT,
        "tool": __version__,
        "schema": ANALYSIS_SCHEMA_VERSION,
        "config": config.model_dump(mode="json"),
        "processes_explicit": processes_file_explicit,
    }
    digest.update(json.dumps(settings, sort_keys=True).encode("utf-8"))
    root = scan_root.resolve()
    for current, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(current) / name
            try:
                stat = path.stat()
            except OSError:
                continue
            relative = path.relative_to(root).as_posix()
            digest.update(f"{relative}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
    if processes_file is not None:
        try:
            stat = processes_file.resolve().stat()
            digest.update(f"processes\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode())
        except OSError:
            digest.update(b"processes\0missing\n")
    return digest.hexdigest()


def analyze_cached(
    path: Path,
    config: AppConfig,
    processes_file: Path | None = None,
    *,
    processes_file_explicit: bool = False,
    cache_dir: Path | None,
) -> tuple[AnalysisResult, bool]:
    """Return (analysis, reused) -- reused is True when the cached result was valid."""
    if cache_dir is None:
        return (
            analyze_path(
                path, config, processes_file, processes_file_explicit=processes_file_explicit
            ),
            False,
        )
    root = path.resolve()
    owner = hashlib.sha256(
        json.dumps(
            {"root": str(root).casefold(), "config": config.model_dump(mode="json")},
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:20]
    fingerprint = input_fingerprint(root, config, processes_file, processes_file_explicit)
    entry = cache_dir / f"{owner}-{fingerprint[:32]}.json.gz"
    cached = _load(entry)
    if cached is not None:
        return cached, True
    analysis = analyze_path(
        path, config, processes_file, processes_file_explicit=processes_file_explicit
    )
    _store(cache_dir, owner, entry, analysis)
    return analysis, False


def _load(entry: Path) -> AnalysisResult | None:
    try:
        payload = gzip.decompress(entry.read_bytes())
        analysis = AnalysisResult.model_validate_json(payload)
    except (OSError, EOFError, ValueError, ValidationError):
        return None
    if analysis.schema_version != ANALYSIS_SCHEMA_VERSION:
        return None
    return analysis


def _store(cache_dir: Path, owner: str, entry: Path, analysis: AnalysisResult) -> None:
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        data = gzip.compress(
            analysis.model_dump_json(exclude_none=True).encode("utf-8"), compresslevel=1
        )
        temp = entry.with_suffix(".tmp")
        temp.write_bytes(data)
        os.replace(temp, entry)
        for stale in cache_dir.glob(f"{owner}-*.json.gz"):
            if stale != entry:
                stale.unlink(missing_ok=True)
    except OSError:
        return  # the cache only saves time; a write failure is not an error
