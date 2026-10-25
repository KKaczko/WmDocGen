"""Stable, file-name-safe IDs for explorer files.

Service and package names may differ only in case, which Windows file systems treat as the
same file, so files are named by a short hash instead. The app never builds a path from a
name: it looks the name up in the search index and fetches by ID.
"""

from __future__ import annotations

import hashlib
import re

ID_LENGTH = 16
ID_RE = re.compile(rf"^[0-9a-f]{{{ID_LENGTH}}}$")


class IdCollisionError(ValueError):
    """Two different names produced the same ID."""


def service_id(package: str, full_name: str) -> str:
    return _digest(f"service\0{package}\0{full_name}")


def package_id(name: str) -> str:
    return _digest(f"package\0{name}")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:ID_LENGTH]


class IdRegistry:
    """Hands out IDs and fails loudly on the (astronomically unlikely) collision."""

    def __init__(self) -> None:
        self._owners: dict[str, str] = {}

    def claim(self, identifier: str, owner: str) -> str:
        existing = self._owners.setdefault(identifier, owner)
        if existing != owner:
            raise IdCollisionError(f"ID {identifier} is shared by {existing!r} and {owner!r}")
        return identifier
