"""Removing generated output safely: only managed paths, never through links.

Shared by `analyze` (Markdown site) and `explorer build`. A managed path is a fixed name
directly under the output root. Symlinks and junctions at that path are unlinked, never
followed, and nothing outside the output root is touched.

Every command that writes files first checks that the path it writes to does not overlap the
analysed packages folder (`check_outside_packages`): analysed packages are never written to,
and a cleanup of an output folder that contains them would delete them.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from wm_doc.graph_publish import _safe_diagnostic


class OutputLocationError(Exception):
    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(f"{code}: {safe_message}")
        self.code = code
        self.safe_message = safe_message


def check_outside_packages(path: Path, packages_root: Path, what: str) -> None:
    """Refuse a path to write to that is, lies inside, or contains the packages folder.

    Paths are compared after resolving links, without regard to case on Windows.
    """
    written = _resolved_parts(path)
    root = _resolved_parts(packages_root)
    if written[: len(root)] == root:
        raise OutputLocationError(
            "OUTPUT_INSIDE_PACKAGES",
            f"The {what} must be outside the analysed packages folder.",
        )
    if root[: len(written)] == written:
        raise OutputLocationError(
            "PACKAGES_INSIDE_OUTPUT",
            f"The analysed packages folder must not be inside the {what}.",
        )


def _resolved_parts(path: Path) -> tuple[str, ...]:
    return tuple(os.path.normcase(part) for part in path.resolve().parts)


class OutputCleanupError(Exception):
    def __init__(self, code: str, safe_message: str, diagnostic: str | None = None) -> None:
        message = f"{code}: {safe_message}"
        if diagnostic:
            message = f"{message} Diagnostic: {diagnostic}"
        super().__init__(message)
        self.code = code
        self.safe_message = message


def remove_managed_path(output: Path, relative_path: Path) -> None:
    target = output / relative_path
    if not target.exists() and not target.is_symlink():
        return
    validate_managed_path(output, target, relative_path)
    try:
        if target.is_symlink():
            target.unlink()
        elif is_junction(target):
            target.rmdir()
        elif target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
    except OSError as exc:
        raise OutputCleanupError(
            "OUTPUT_CLEANUP_FAILED",
            f"Could not remove managed generated output path `{relative_path.as_posix()}`.",
            _safe_diagnostic(str(exc), output),
        ) from exc


def validate_managed_path(output: Path, target: Path, relative_path: Path) -> None:
    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise OutputCleanupError(
            "OUTPUT_PATH_UNSAFE",
            f"Managed generated output path `{relative_path.as_posix()}` is unsafe.",
        )
    output_root = output.absolute()
    try:
        target.absolute().relative_to(output_root)
    except ValueError as exc:
        raise OutputCleanupError(
            "OUTPUT_PATH_UNSAFE",
            f"Managed generated output path `{relative_path.as_posix()}` escaped the output root.",
        ) from exc


def is_junction(path: Path) -> bool:
    is_junction_method = getattr(path, "is_junction", None)
    return bool(is_junction_method and is_junction_method())
