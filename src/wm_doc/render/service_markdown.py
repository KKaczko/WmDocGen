from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

from jinja2 import Template

from wm_doc.ir import (
    CallOccurrence,
    DependencyKind,
    FlowNode,
    FlowService,
    SignatureField,
    UniqueDependency,
)

IMPORTANCE_ORDER = {"IMPORTANT": 0, "NORMAL": 1, "LOW": 2}
MAX_OUTLINE_DEPTH = 5
MAX_OUTLINE_ROWS = 80

_TEMPLATE = Template(
    """# {{ service.identity.full_name }}

## Identity

| Field | Value |
| --- | --- |
| Package | `{{ service.identity.package }}` |
| Namespace | `{{ service.identity.namespace }}` |
| Service | `{{ service.identity.name }}` |
| Type | `{{ service.service_type }}` |
| Importance | `{{ service.classification.importance }}` |
| Layer | `{{ service.classification.layer }}` |
| Identity basis | `{{ service.identity.basis }}` |

## Description

{% if service.description -%}
Extracted description:

{{ service.description }}
{% else -%}
No description was declared in supported metadata.
{% endif %}

## Input Signature

{{ render_fields(service.signature.inputs) }}

## Output Signature

{{ render_fields(service.signature.outputs) }}

## FLOW Overview

| Metric | Count |
| --- | ---: |
| Sequences | {{ flow_count("SEQUENCE") }} |
| Branches | {{ flow_count("BRANCH") }} |
| Loops | {{ flow_count("LOOP") }} |
| Exits | {{ flow_count("EXIT") }} |
| Call occurrences | {{ service.metrics.call_occurrence_count }} |
| Unique dependencies | {{ service.metrics.unique_dependency_count }} |

## Normal Service Dependencies

{{ render_dependencies(normal_dependencies) }}

## Transformer Dependencies

{{ render_dependencies(transformer_dependencies) }}

## Call Occurrences

{{ render_calls(service_calls, "INVOKE") }}

## Transformer Call Occurrences

{{ render_calls(transformer_calls, "MAPINVOKE") }}

## FLOW Outline

{{ flow_outline }}

## Unsupported Or Unknown Constructs

{% if service.findings -%}
{% for finding in service.findings -%}
- {{ finding.status }} `{{ finding.code }}` at `{{ finding.source.path }}`: {{ finding.message }}
{% endfor %}
{% else -%}
No service-level findings.
{% endif %}

## Source Evidence

- Service metadata: `{{ service.source.path }}`
- Signature metadata: `{{ service.signature.source.path }}`
{% for call in service.call_occurrences[:20] -%}
- {{ call.call_type }} `{{ call.id }}` target `{{ call.target }}`:
  `{{ call.source.path }}`{% if call.source.line %}:{{ call.source.line }}{% endif %}
{% endfor -%}
{% if service.call_occurrences|length > 20 %}
- Source evidence list truncated after 20 call occurrences in Markdown.
  Full evidence is in `analysis.json`.
{% endif %}

## Analysis Limitations

M2a extracts declared signatures, an ordered FLOW tree, typed `EXIT` nodes, static
`INVOKE` calls and static `MAPINVOKE` transformer calls. It does not interpret
MAP data-flow semantics, evaluate branch conditions, simulate loops or runtime state,
resolve dynamic invocation targets, execute Java code, or connect to Integration Server.
""",
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_service_markdown(service: FlowService) -> str:
    normal_dependencies = _dependencies_for_kind(service, DependencyKind.INVOKES)
    transformer_dependencies = _dependencies_for_kind(service, DependencyKind.USES_TRANSFORMER)
    service_calls = _calls_for_type(service, "INVOKE")
    transformer_calls = _calls_for_type(service, "MAPINVOKE")
    return _TEMPLATE.render(
        service=service,
        normal_dependencies=normal_dependencies,
        transformer_dependencies=transformer_dependencies,
        service_calls=service_calls,
        transformer_calls=transformer_calls,
        flow_outline=_flow_outline(service.flow_tree),
        flow_count=lambda name: service.metrics.flow_node_counts.get(name, 0),
        render_fields=_render_fields,
        render_dependencies=_render_dependencies,
        render_calls=_render_calls,
    )


def service_markdown_filename(full_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", full_name)
    return f"{slug}.md"


def _dependencies_for_kind(
    service: FlowService, dependency_kind: DependencyKind
) -> list[UniqueDependency]:
    dependencies = [
        dependency
        for dependency in service.unique_dependencies
        if dependency.dependency_kind == dependency_kind
    ]
    return sorted(
        dependencies,
        key=lambda dependency: (
            IMPORTANCE_ORDER.get(dependency.target_classification.importance.value, 99),
            dependency.target_service.casefold(),
            dependency.id,
        ),
    )


def _calls_for_type(service: FlowService, call_type: str) -> list[CallOccurrence]:
    return [call for call in service.call_occurrences if call.call_type.value == call_type]


def _render_dependencies(dependencies: list[UniqueDependency]) -> str:
    if not dependencies:
        return "No static targets were extracted for this dependency kind.\n"
    lines = [
        "| Occurrences | Resolved | Target |",
        "| ---: | --- | --- |",
    ]
    for dependency in dependencies:
        lines.append(
            "| "
            f"{dependency.occurrence_count} | "
            f"{dependency.resolved} | "
            f"`{dependency.target_service}` |"
        )
    return "\n".join(lines) + "\n"


def _render_calls(calls: list[CallOccurrence], label: str) -> str:
    if not calls:
        return f"No static {label} call occurrences were extracted.\n"
    lines = [
        "| Call | Resolved | Target | Source |",
        "| --- | --- | --- | --- |",
    ]
    for call in calls[:40]:
        line = f":{call.source.line}" if call.source.line else ""
        lines.append(
            "| "
            f"`{call.id}` | "
            f"{call.resolved} | "
            f"`{call.target}` | "
            f"`{call.source.path}{line}` |"
        )
    if len(calls) > 40:
        lines.append(f"| ... | ... | {len(calls) - 40} additional calls omitted | ... |")
    return "\n".join(lines) + "\n"


def _flow_outline(flow_tree: FlowNode | None) -> str:
    if flow_tree is None:
        return "No FLOW tree was extracted.\n"
    lines: list[str] = []
    truncated = False

    def visit(node: FlowNode, depth: int) -> None:
        nonlocal truncated
        if truncated:
            return
        if len(lines) >= MAX_OUTLINE_ROWS:
            truncated = True
            return
        indent = "  " * depth
        detail_parts = []
        if node.label:
            detail_parts.append(node.label)
        if node.target:
            detail_parts.append(f"target={node.target}")
        if node.switch:
            detail_parts.append(f"switch={node.switch}")
        if node.in_array:
            detail_parts.append(f"in={node.in_array}")
        if node.exit_from:
            detail_parts.append(f"from={node.exit_from}")
        detail = f" ({'; '.join(detail_parts)})" if detail_parts else ""
        lines.append(f"- {indent}`{node.id}` {node.type.value}{detail}")
        if depth >= MAX_OUTLINE_DEPTH:
            if node.children:
                lines.append(f"- {indent}  ... depth limit reached")
            return
        for child in node.children:
            visit(child, depth + 1)

    visit(flow_tree, 0)
    if truncated:
        lines.append(f"- ... outline truncated after {MAX_OUTLINE_ROWS} rows")
    return "\n".join(lines) + "\n"


def _render_fields(fields: list[SignatureField]) -> str:
    if not fields:
        return "No fields declared in supported metadata.\n"
    lines = [
        "| Field | Type | Dim | Optional | Document Reference |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for field in fields:
        _append_field(lines, field, 0)
    return "\n".join(lines) + "\n"


def _append_field(lines: list[str], field: SignatureField, depth: int) -> None:
    prefix = "  " * depth
    lines.append(
        "| "
        f"`{prefix}{field.name}` | "
        f"`{field.data_type or ''}` | "
        f"{field.dimensions if field.dimensions is not None else ''} | "
        f"{field.optional if field.optional is not None else ''} | "
        f"`{field.document_reference or ''}` |"
    )
    for child in field.children:
        _append_field(lines, child, depth + 1)


def write_service_markdown(output_dir: Path, services: list[FlowService]) -> list[Path]:
    service_dir = output_dir / "services"
    service_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    slug_counts = Counter(
        service_markdown_filename(service.identity.full_name) for service in services
    )
    for service in sorted(services, key=lambda item: item.identity.full_name.casefold()):
        filename = service_markdown_filename(service.identity.full_name)
        if slug_counts[filename] > 1:
            stem = filename.removesuffix(".md")
            digest = hashlib.sha256(service.identity.full_name.encode("utf-8")).hexdigest()[:12]
            filename = f"{stem}__{digest}.md"
        path = service_dir / filename
        path.write_text(render_service_markdown(service), encoding="utf-8")
        written.append(path)
    return written
