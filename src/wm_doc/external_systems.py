"""Curated catalog of external systems an integration talks to.

A package's most business-relevant dependencies are the ones the analyzer can never
resolve: a call to `sara.services:createCustomer` leaves the snapshot entirely, so
static analysis can only report `not in this snapshot`. The operator, however, knows
that namespace belongs to a core system of record.

This module lets that knowledge be declared once, as bounded structured data, and
attached deterministically to the dependencies it explains. It is a fixed
name-to-fact lookup in the same spirit as :mod:`wm_doc.builtins` -- not RAG, not
free-form document ingestion, and never a source of inferred behaviour. An
unmatched external dependency keeps its existing "outside this snapshot" treatment.
"""

from __future__ import annotations

from enum import StrEnum
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

MAX_SYSTEMS = 100
MAX_DESCRIPTION_CHARS = 500


class ExternalSystemKind(StrEnum):
    """Coarse classification, used for wording and never for inferring behaviour."""

    CORE_SYSTEM = "CORE_SYSTEM"
    GOVERNMENT_REGISTRY = "GOVERNMENT_REGISTRY"
    PROCESS_ENGINE = "PROCESS_ENGINE"
    PARTNER = "PARTNER"
    MESSAGING = "MESSAGING"
    DATABASE = "DATABASE"
    OTHER = "OTHER"


class ExternalSystem(BaseModel):
    """One declared external system and the namespaces that reach it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    kind: ExternalSystemKind = ExternalSystemKind.OTHER
    vendor: str | None = None
    description: str = ""
    namespaces: list[str] = Field(default_factory=list)

    def matches(self, target_service: str) -> bool:
        """Report whether *target_service* (`namespace:service`) belongs to this system."""
        namespace = target_service.split(":", 1)[0].casefold()
        full = target_service.casefold()
        return any(
            fnmatchcase(namespace, pattern.casefold())
            or fnmatchcase(full, pattern.casefold())
            for pattern in self.namespaces
        )


class ExternalSystemCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    systems: list[ExternalSystem] = Field(default_factory=list)

    def match(self, target_service: str) -> ExternalSystem | None:
        """Return the first declared system owning *target_service*, or None."""
        for system in self.systems:
            if system.matches(target_service):
                return system
        return None


EMPTY_CATALOG = ExternalSystemCatalog()


class ExternalSystemsError(ValueError):
    """Raised when a declared catalog cannot be used as written."""


def load_external_systems(path: Path | None) -> ExternalSystemCatalog:
    """Load and validate a declared catalog, or return the empty one when absent."""
    if path is None:
        return EMPTY_CATALOG
    try:
        raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ExternalSystemsError("External systems file could not be read.") from exc
    except yaml.YAMLError as exc:
        raise ExternalSystemsError("External systems file is not valid YAML.") from exc
    if raw is None:
        return EMPTY_CATALOG
    if not isinstance(raw, dict):
        raise ExternalSystemsError("External systems file must contain a mapping.")

    catalog = ExternalSystemCatalog.model_validate(raw)
    if len(catalog.systems) > MAX_SYSTEMS:
        raise ExternalSystemsError(
            f"External systems file declares more than {MAX_SYSTEMS} systems."
        )
    seen: set[str] = set()
    for system in catalog.systems:
        if not system.id or not system.name:
            raise ExternalSystemsError("Each external system needs an id and a name.")
        if system.id.casefold() in seen:
            raise ExternalSystemsError(f"Duplicate external system id `{system.id}`.")
        seen.add(system.id.casefold())
        if not system.namespaces:
            raise ExternalSystemsError(
                f"External system `{system.id}` declares no namespaces to match."
            )
        if len(system.description) > MAX_DESCRIPTION_CHARS:
            raise ExternalSystemsError(
                f"External system `{system.id}` description exceeds "
                f"{MAX_DESCRIPTION_CHARS} characters."
            )
    return catalog


def system_label(system: ExternalSystem) -> str:
    """Short human label for a dependency table cell."""
    return f"{system.name} ({system.vendor})" if system.vendor else system.name
