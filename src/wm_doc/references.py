"""Schema-free references from non-service artifacts to known nodes.

Triggers, REST and SOAP descriptors, adapter services and connections all store the names
of the services, document types and connections they use somewhere in their node.ndf.
Their exact layouts are product-specific and not modelled here. Instead every string value
is compared with the set of known full names; an exact match is recorded together with
the key path where it was found. Nothing is inferred from partial matches or key names,
and no value other than a matched name is ever kept.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from wm_doc.ir import ArtifactReference, ReferenceTargetKind, SourceReference
from wm_doc.values import parse_values_file
from wm_doc.xmlsafe import XmlParseError, XmlSecurityError

MAX_REFERENCES_PER_ARTIFACT = 50


def iter_string_values(data: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Yield (key path, value) for every string in parsed Values data."""
    if isinstance(data, str):
        yield path, data
    elif isinstance(data, dict):
        for key in sorted(data):
            child_path = f"{path}/{key}" if path else str(key)
            yield from iter_string_values(data[key], child_path)
    elif isinstance(data, list):
        for item in data:
            yield from iter_string_values(item, f"{path}[]")


def find_references(
    scan_root: Path,
    sources: list[tuple[str, str, SourceReference]],
    known: dict[str, ReferenceTargetKind],
) -> list[ArtifactReference]:
    """Scan each source node.ndf for values that exactly equal a known full name.

    `sources` holds (artifact full name, artifact kind, node.ndf source reference).
    """
    references: list[ArtifactReference] = []
    for source_name, source_kind, source in sources:
        node_path = (scan_root / source.path).resolve()
        if node_path.name != "node.ndf" or not node_path.is_file():
            continue
        try:
            node_path.relative_to(scan_root.resolve())
            values = parse_values_file(node_path)
        except (ValueError, XmlParseError, XmlSecurityError, OSError):
            continue
        seen: set[tuple[str, str]] = set()
        for key_path, value in iter_string_values(values):
            target = value.strip()
            kind = known.get(target)
            if kind is None or target == source_name or (target, key_path) in seen:
                continue
            seen.add((target, key_path))
            references.append(
                ArtifactReference(
                    source_name=source_name,
                    source_kind=source_kind,
                    target_name=target,
                    target_kind=kind,
                    key_path=key_path,
                    source=source,
                )
            )
            if len(seen) >= MAX_REFERENCES_PER_ARTIFACT:
                break
    return sorted(
        references,
        key=lambda item: (
            item.source_name.casefold(),
            item.target_name.casefold(),
            item.key_path,
        ),
    )
