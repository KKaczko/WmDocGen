"""Key-path shapes of non-service artifacts, without any values.

Run on production, this shows how triggers, REST/SOAP descriptors, adapter services and
connections are laid out in node.ndf -- which keys exist, how often, and whether a key's
value is the name of a known service, document type or artifact -- so targeted parsers can
be designed without copying production files. Only key names and counts are printed.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from wm_doc.ir import AnalysisResult, ServiceType
from wm_doc.references import iter_string_values
from wm_doc.render.artifact_markdown import artifact_kind
from wm_doc.values import parse_values_file
from wm_doc.xmlsafe import XmlParseError, XmlSecurityError

MAX_KEY_PATHS_PER_KIND = 200


def render_shapes(analysis: AnalysisResult, scan_root: Path) -> str:
    known: dict[str, str] = {}
    for artifact in analysis.namespace_artifacts:
        known[artifact.full_name] = "artifact"
    for document in analysis.document_types:
        known[document.identity.full_name] = "document"
    for package in analysis.packages:
        for service in package.services:
            known[service.identity.full_name] = "service"

    sources: list[tuple[str, str]] = [
        (artifact_kind(artifact), artifact.source.path)
        for artifact in analysis.namespace_artifacts
        if artifact.probable_type != "specification"
    ]
    sources.extend(
        (f"service ({service.source_service_type or 'opaque'})", service.source.path)
        for package in analysis.packages
        for service in package.services
        if service.service_type is ServiceType.OPAQUE
    )

    artifacts_per_kind: Counter[str] = Counter()
    paths: dict[str, Counter[str]] = defaultdict(Counter)
    names: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    root = scan_root.resolve()
    for kind, relative in sources:
        node_path = (root / relative).resolve()
        if node_path.name != "node.ndf" or not node_path.is_file():
            continue
        try:
            node_path.relative_to(root)
            values = parse_values_file(node_path)
        except (ValueError, XmlParseError, XmlSecurityError, OSError):
            continue
        artifacts_per_kind[kind] += 1
        seen: set[str] = set()
        for key_path, value in iter_string_values(values):
            if key_path not in seen:
                seen.add(key_path)
                paths[kind][key_path] += 1
            target_kind = known.get(value.strip())
            if target_kind is not None:
                names[kind][key_path][target_kind] += 1

    lines = [
        "# wm-doc artifact shapes",
        "",
        (
            "Key paths found in node.ndf, per artifact type. Values are never printed; the "
            "last column only says how often a key holds the exact name of a known service, "
            "document type or artifact."
        ),
        "",
    ]
    if not artifacts_per_kind:
        return "\n".join([*lines, "No non-service artifacts were found.", ""])
    for kind in sorted(artifacts_per_kind, key=str.casefold):
        lines += [
            f"## `{kind}` ({artifacts_per_kind[kind]} artifact(s))",
            "",
            "| Key path | Artifacts | Holds a known name |",
            "| --- | ---: | --- |",
        ]
        ranked = sorted(paths[kind].items(), key=lambda item: (-item[1], item[0]))
        for key_path, count in ranked[:MAX_KEY_PATHS_PER_KIND]:
            held = names[kind].get(key_path)
            held_text = (
                ", ".join(f"{target} x{n}" for target, n in sorted(held.items())) if held else ""
            )
            lines.append(f"| `{key_path}` | {count} | {held_text} |")
        if len(ranked) > MAX_KEY_PATHS_PER_KIND:
            lines.append(f"| ... {len(ranked) - MAX_KEY_PATHS_PER_KIND} more | | |")
        lines.append("")
    return "\n".join(lines)
