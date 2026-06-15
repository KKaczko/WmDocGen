from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Template

from wm_doc.ir import FlowService, SignatureField

IMPORTANCE_ORDER = {"IMPORTANT": 0, "NORMAL": 1, "LOW": 2}

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

## Static Invoked Services

{% if dependencies -%}
| Invoke | Resolved | Target |
| --- | --- | --- |
{% for edge in dependencies -%}
| `{{ edge.invoke_id }}` | {{ edge.resolved }} | `{{ edge.target_service }}` |
{% endfor %}
{% else -%}
No static INVOKE targets were extracted.
{% endif %}

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
{% for invoke in service.invokes -%}
- Invoke `{{ invoke.id }}` target `{{ invoke.target }}`: `{{ invoke.source.path }}`
{% endfor %}

## Analysis Limitations

M1 extracts declared signatures, structural container paths and static `INVOKE`/`MAPINVOKE`
targets. It does not interpret MAP transformations, branch semantics, EXIT behavior, retry
semantics, dynamic invocation targets, Java code, adapter metadata, triggers or process models.
""",
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_service_markdown(service: FlowService) -> str:
    dependencies = sorted(
        service.dependencies,
        key=lambda edge: (
            IMPORTANCE_ORDER.get(edge.target_classification.importance.value, 99),
            edge.invoke_id,
            edge.target_service.casefold(),
        ),
    )
    return _TEMPLATE.render(
        service=service, dependencies=dependencies, render_fields=_render_fields
    )


def service_markdown_filename(full_name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", full_name)
    return f"{slug}.md"


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
    for service in sorted(services, key=lambda item: item.identity.full_name.casefold()):
        path = service_dir / service_markdown_filename(service.identity.full_name)
        path.write_text(render_service_markdown(service), encoding="utf-8")
        written.append(path)
    return written
