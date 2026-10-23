"""Catalog of webMethods platform (``pub.*`` / ``wm.*``) service descriptions and effects.

Built-in services live in the product packages (WmPublic, WmART, WmJDBCAdapter, ...), which
are never analysed, so a call to one can never be resolved from the packages. The catalog
gives each known platform service a one-line description and an effect family:
``pub.art.transaction:startTransaction`` means the service is transactional, and
``pub.publish:publish`` means it emits a message.

The entries live in ``data/platform_services.yml``. A user file passed with
``--platform-services`` adds or overrides entries (`use_platform_catalog`). This is a fixed
name-to-description lookup; nothing is inferred for a name the catalog does not know --
unknown built-ins keep their unresolved treatment and are listed by `stats`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

BUILTIN_PREFIXES = ("pub.", "wm.")


class BuiltinFamily(StrEnum):
    """Coarse effect family used to derive a service layer and summary sentence."""

    TRANSACTION = "TRANSACTION"
    DATABASE = "DATABASE"
    MESSAGING = "MESSAGING"
    REMOTE = "REMOTE"
    FILE = "FILE"
    IO = "IO"
    XML = "XML"
    JSON = "JSON"
    FLAT_FILE = "FLAT_FILE"
    DOCUMENT = "DOCUMENT"
    STRING = "STRING"
    DATE = "DATE"
    NUMERIC = "NUMERIC"
    LIST = "LIST"
    ERROR_HANDLING = "ERROR_HANDLING"
    LOGGING = "LOGGING"
    STORAGE = "STORAGE"
    FLOW_CONTROL = "FLOW_CONTROL"
    SECURITY = "SECURITY"
    SCHEMA = "SCHEMA"
    SERVER_ADMIN = "SERVER_ADMIN"


# How much each family matters to a reader deciding what a service does, most first.
# Summaries list effects in this order instead of call order, so a publish is not
# crowded out by list or string helpers that happen to run earlier.
FAMILY_RANK: dict[BuiltinFamily, int] = {
    family: rank
    for rank, family in enumerate(
        (
            BuiltinFamily.TRANSACTION,
            BuiltinFamily.DATABASE,
            BuiltinFamily.MESSAGING,
            BuiltinFamily.REMOTE,
            BuiltinFamily.FILE,
            BuiltinFamily.STORAGE,
            BuiltinFamily.SERVER_ADMIN,
            BuiltinFamily.SECURITY,
            BuiltinFamily.SCHEMA,
            BuiltinFamily.FLAT_FILE,
            BuiltinFamily.XML,
            BuiltinFamily.JSON,
            BuiltinFamily.DOCUMENT,
            BuiltinFamily.IO,
            BuiltinFamily.DATE,
            BuiltinFamily.NUMERIC,
            BuiltinFamily.STRING,
            BuiltinFamily.LIST,
            BuiltinFamily.FLOW_CONTROL,
            BuiltinFamily.LOGGING,
            BuiltinFamily.ERROR_HANDLING,
        )
    )
}


@dataclass(frozen=True)
class DataEffectSpec:
    """How a platform call touches data outside the pipeline, and where to look for it.

    `object_inputs` and `where_inputs` name documented input fields; when a FLOW sets or
    maps one of them, the value (or its source path) identifies the object or location.
    A field the FLOW does not set simply yields "not determined" -- nothing is guessed.
    """

    object_label: str
    system: str
    object_inputs: tuple[str, ...] = ()
    where_inputs: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuiltinEffect:
    """A plain-language effect for one documented platform service."""

    label: str
    family: BuiltinFamily
    data: DataEffectSpec | None = None


def is_builtin_name(full_name: str) -> bool:
    """Report whether *full_name* addresses the platform rather than a package."""
    return full_name.casefold().startswith(BUILTIN_PREFIXES)


MAX_DESCRIPTION_CHARS = 120
MAX_USER_ENTRIES = 5_000
_DATA_KEYS = {"object", "system", "object_inputs", "where_inputs"}
_ENTRY_KEYS = {"name", "description", "family", "data"}


class PlatformServicesError(ValueError):
    """Raised when a platform services file cannot be used as written."""


def parse_platform_services(text: str, origin: str) -> dict[str, BuiltinEffect]:
    """Validate a platform services YAML document; return name (case-folded) -> effect."""
    try:
        raw: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PlatformServicesError(f"{origin} is not valid YAML.") from exc
    if raw is None:
        return {}
    items = raw.get("services") if isinstance(raw, dict) else None
    if not isinstance(items, list):
        raise PlatformServicesError(f"{origin} must contain a `services:` list.")
    if len(items) > MAX_USER_ENTRIES:
        raise PlatformServicesError(f"{origin} lists more than {MAX_USER_ENTRIES} services.")
    catalog: dict[str, BuiltinEffect] = {}
    for item in items:
        name, effect = _entry(item, origin)
        key = name.casefold()
        if key in catalog:
            raise PlatformServicesError(f"{origin} lists `{name}` twice.")
        catalog[key] = effect
    return catalog


def _entry(item: Any, origin: str) -> tuple[str, BuiltinEffect]:
    if not isinstance(item, dict) or set(item) - _ENTRY_KEYS:
        raise PlatformServicesError(
            f"{origin}: each service needs only name, description, family and data."
        )
    name = str(item.get("name") or "").strip()
    if not is_builtin_name(name) or ":" not in name:
        raise PlatformServicesError(
            f"{origin}: `{name or '?'}` is not a platform service name (pub.* or wm.*); "
            "use external-systems.yml for services of other packages."
        )
    description = " ".join(str(item.get("description") or "").split())
    if not description or len(description) > MAX_DESCRIPTION_CHARS:
        raise PlatformServicesError(
            f"{origin}: `{name}` needs a description of 1 to {MAX_DESCRIPTION_CHARS} characters."
        )
    try:
        family = BuiltinFamily(str(item.get("family") or "").strip().upper())
    except ValueError as exc:
        raise PlatformServicesError(f"{origin}: `{name}` has an unknown family.") from exc
    return name, BuiltinEffect(label=description, family=family, data=_data(item, name, origin))


def _data(item: dict[str, Any], name: str, origin: str) -> DataEffectSpec | None:
    data = item.get("data")
    if data is None:
        return None
    if not isinstance(data, dict) or set(data) - _DATA_KEYS:
        raise PlatformServicesError(
            f"{origin}: `{name}` data takes only object, system, object_inputs, where_inputs."
        )
    object_label = str(data.get("object") or "").strip()
    system = str(data.get("system") or "").strip()
    if not object_label or not system:
        raise PlatformServicesError(f"{origin}: `{name}` data needs an object and a system.")
    fields: dict[str, tuple[str, ...]] = {}
    for key in ("object_inputs", "where_inputs"):
        value = data.get(key) or []
        if not isinstance(value, list) or not all(isinstance(x, str) and x for x in value):
            raise PlatformServicesError(f"{origin}: `{name}` {key} must be a list of names.")
        fields[key] = tuple(value)
    return DataEffectSpec(
        object_label,
        system,
        object_inputs=fields["object_inputs"],
        where_inputs=fields["where_inputs"],
    )


def load_platform_services(path: Path) -> dict[str, BuiltinEffect]:
    """Read a user platform services file (same format as the shipped catalog)."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PlatformServicesError("Platform services file could not be read.") from exc
    return parse_platform_services(text, "Platform services file")


SHIPPED_SERVICES: dict[str, BuiltinEffect] = parse_platform_services(
    resources.files("wm_doc").joinpath("data/platform_services.yml").read_text(encoding="utf-8"),
    "Shipped platform services catalog",
)
# The catalog in use: the shipped entries, plus a user file once `use_platform_catalog` ran.
BUILTIN_SERVICES: dict[str, BuiltinEffect] = dict(SHIPPED_SERVICES)


def use_platform_catalog(extra: Path | None) -> int:
    """Reset to the shipped catalog and add the entries of *extra*; return how many it had."""
    added = load_platform_services(extra) if extra is not None else {}
    BUILTIN_SERVICES.clear()
    BUILTIN_SERVICES.update(SHIPPED_SERVICES)
    BUILTIN_SERVICES.update(added)
    return len(added)


def builtin_effect(full_name: str) -> BuiltinEffect | None:
    """Return the catalogued effect for *full_name*, or None when it is not known."""
    return BUILTIN_SERVICES.get(full_name.casefold())
