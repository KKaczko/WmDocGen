from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

from jinja2 import Template

from wm_doc.ir import (
    CallOccurrence,
    DependencyKind,
    DocumentReferenceOccurrence,
    FlowNode,
    FlowService,
    LiteralValue,
    MappingEndpoint,
    MappingOperation,
    ServiceDocumentDependency,
    SignatureField,
    SourceReference,
    TextValue,
    TransformerBinding,
    UniqueDependency,
)
from wm_doc.render.document_markdown import document_markdown_filename

IMPORTANCE_ORDER = {"IMPORTANT": 0, "NORMAL": 1, "LOW": 2}
MAX_OUTLINE_DEPTH = 5
MAX_OUTLINE_ROWS = 80
MAX_MAPPING_ROWS = 50

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

{% if description_text -%}
Extracted description:

{{ description_text }}
{% else -%}
No description was declared in supported metadata.
{% endif %}

## Input Signature

{{ render_fields(service.signature.inputs) }}

## Output Signature

{{ render_fields(service.signature.outputs) }}

## Document Type Usage

### Input Document Types

{{ render_document_usage(input_document_dependencies) }}

### Output Document Types

{{ render_document_usage(output_document_dependencies) }}

### Resolved Document References

{{ render_document_references(resolved_document_references) }}

### Unresolved Document References

{{ render_document_references(unresolved_document_references) }}

## FLOW Overview

| Metric | Count |
| --- | ---: |
| Sequences | {{ flow_count("SEQUENCE") }} |
| Branches | {{ flow_count("BRANCH") }} |
| Loops | {{ flow_count("LOOP") }} |
| Exits | {{ flow_count("EXIT") }} |
| Call occurrences | {{ service.metrics.call_occurrence_count }} |
| Unique dependencies | {{ service.metrics.unique_dependency_count }} |

## Mapping Overview

| Metric | Count |
| --- | ---: |
| Flow maps | {{ service.metrics.flow_map_count }} |
| Copy operations | {{ mapping_count("COPY") }} |
| Set operations | {{ mapping_count("SET") }} |
| Delete operations | {{ mapping_count("DELETE") }} |
| Transformer bindings | {{ service.metrics.transformer_binding_count }} |
| Transformer input bindings | {{ binding_count("INTO_TRANSFORMER") }} |
| Transformer output bindings | {{ binding_count("FROM_TRANSFORMER") }} |
| Partially interpreted mappings | {{ service.metrics.partially_interpreted_mapping_count }} |
| Literal policy | `{{ service.extraction_policy.literal_mode }}` |
| Free-text policy | `{{ service.extraction_policy.free_text_mode }}` |

## Mapping Copies

{{ render_mapping_operations(copy_operations, "COPY") }}

## Mapping Sets

{{ render_mapping_operations(set_operations, "SET") }}

## Mapping Deletes

{{ render_mapping_operations(delete_operations, "DELETE") }}

## Transformer Bindings

{{ render_transformer_bindings(service.transformer_bindings) }}

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

{% if service.findings %}
{% for finding in service.findings %}
- {{ finding.status }} `{{ finding.code }}` at `{{ finding.source.path }}`: {{ finding.message }}
{% endfor %}
{% else %}
No service-level findings.
{% endif %}

## Source Evidence

- Service metadata: `{{ service.source.path }}`
- Signature metadata: `{{ service.signature.source.path }}`
{% for call in service.call_occurrences[:20] %}
- {{ call.call_type }} `{{ call.id }}` target `{{ call.target }}`:
  `{{ call.source.path }}`{% if call.source.line %}:{{ call.source.line }}{% endif %}
{% endfor %}
{% if service.call_occurrences|length > 20 %}
- Source evidence list truncated after 20 call occurrences in Markdown.
  Full evidence is in `analysis.json`.
{% endif %}

## Analysis Limitations

M2b extracts observed MAP copy, set, delete and transformer binding evidence with literal
disclosure policies. It does not resolve mapped paths against document schemas, evaluate branch
conditions, simulate loops or runtime state, resolve dynamic invocation targets, execute Java code,
or connect to Integration Server.
""",
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_service_markdown(service: FlowService) -> str:
    normal_dependencies = _dependencies_for_kind(service, DependencyKind.INVOKES)
    transformer_dependencies = _dependencies_for_kind(service, DependencyKind.USES_TRANSFORMER)
    service_calls = _calls_for_type(service, "INVOKE")
    transformer_calls = _calls_for_type(service, "MAPINVOKE")
    input_document_dependencies = [
        dependency
        for dependency in service.service_document_dependencies
        if dependency.usage_role.value in {"INPUT", "INPUT_OUTPUT"}
    ]
    output_document_dependencies = [
        dependency
        for dependency in service.service_document_dependencies
        if dependency.usage_role.value in {"OUTPUT", "INPUT_OUTPUT"}
    ]
    resolved_document_references = [
        reference for reference in service.document_reference_occurrences if reference.resolved
    ]
    unresolved_document_references = [
        reference for reference in service.document_reference_occurrences if not reference.resolved
    ]
    copy_operations = _operations_for_type(service, "COPY")
    set_operations = _operations_for_type(service, "SET")
    delete_operations = _operations_for_type(service, "DELETE")
    description_text = _text_display(service.description)
    return _TEMPLATE.render(
        service=service,
        description_text=description_text,
        normal_dependencies=normal_dependencies,
        transformer_dependencies=transformer_dependencies,
        service_calls=service_calls,
        transformer_calls=transformer_calls,
        input_document_dependencies=input_document_dependencies,
        output_document_dependencies=output_document_dependencies,
        resolved_document_references=resolved_document_references,
        unresolved_document_references=unresolved_document_references,
        copy_operations=copy_operations,
        set_operations=set_operations,
        delete_operations=delete_operations,
        flow_outline=_flow_outline(service.flow_tree),
        flow_count=lambda name: service.metrics.flow_node_counts.get(name, 0),
        mapping_count=lambda name: service.metrics.mapping_operation_type_counts.get(name, 0),
        binding_count=lambda name: service.metrics.transformer_binding_direction_counts.get(
            name, 0
        ),
        render_fields=_render_fields,
        render_dependencies=_render_dependencies,
        render_document_usage=_render_document_usage,
        render_document_references=_render_document_references,
        render_calls=_render_calls,
        render_mapping_operations=_render_mapping_operations,
        render_transformer_bindings=_render_transformer_bindings,
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


def _operations_for_type(service: FlowService, operation_type: str) -> list[MappingOperation]:
    return [
        operation
        for operation in service.mapping_operations
        if operation.operation_type.value == operation_type
    ]


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


def _render_document_usage(dependencies: list[ServiceDocumentDependency]) -> str:
    if not dependencies:
        return "No document dependencies were extracted for this usage role.\n"
    lines = [
        "| Usage | Resolved | Document | Occurrences |",
        "| --- | --- | --- | ---: |",
    ]
    for dependency in sorted(
        dependencies,
        key=lambda item: (
            item.usage_role.value,
            item.target_document.casefold(),
            item.id,
        ),
    ):
        document = _document_link(dependency.target_document, dependency.resolved)
        lines.append(
            "| "
            f"`{dependency.usage_role.value}` | "
            f"{dependency.resolved} | "
            f"{document} | "
            f"{dependency.occurrence_count} |"
        )
    return "\n".join(lines) + "\n"


def _render_document_references(references: list[DocumentReferenceOccurrence]) -> str:
    if not references:
        return "No document reference occurrences were extracted for this section.\n"
    lines = [
        "| Usage | Field | Resolved | Target | Source |",
        "| --- | --- | --- | --- | --- |",
    ]
    for reference in sorted(
        references,
        key=lambda item: (
            item.usage_role.value if item.usage_role else "",
            item.source_field_path.casefold(),
            item.declared_target.casefold(),
            item.id,
        ),
    ):
        source = reference.source.path + (
            f":{reference.source.line}" if reference.source.line else ""
        )
        lines.append(
            "| "
            f"`{reference.usage_role.value if reference.usage_role else ''}` | "
            f"`{reference.source_field_path}` | "
            f"{reference.resolved} | "
            f"{_document_link(reference.declared_target, reference.resolved)} | "
            f"`{source}` |"
        )
    return "\n".join(lines) + "\n"


def _document_link(full_name: str, resolved: bool) -> str:
    if not resolved:
        return f"`{full_name}`"
    filename = document_markdown_filename(full_name)
    return f"[`{full_name}`](../documents/{filename})"


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


def _render_mapping_operations(operations: list[MappingOperation], label: str) -> str:
    if not operations:
        return f"No {label} mapping operations were extracted.\n"
    lines = [
        "| Operation | Source | Target | Literal | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for operation in operations[:MAX_MAPPING_ROWS]:
        source = _endpoint_display(operation.source_endpoint or operation.delete_endpoint)
        target = _endpoint_display(operation.target_endpoint or operation.delete_endpoint)
        lines.append(
            "| "
            f"`{operation.id}` | "
            f"{source} | "
            f"{target} | "
            f"{_literal_display(operation.literal)} | "
            f"`{_source_display(operation.source)}` |"
        )
    if len(operations) > MAX_MAPPING_ROWS:
        omitted = len(operations) - MAX_MAPPING_ROWS
        lines.append(f"| ... | ... | ... | {omitted} additional operations omitted | ... |")
    return "\n".join(lines) + "\n"


def _render_transformer_bindings(bindings: list[TransformerBinding]) -> str:
    if not bindings:
        return "No MAPINVOKE transformer bindings were extracted.\n"
    lines = [
        "| Binding | Direction | Transformer | Pipeline | Literal | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for binding in bindings[:MAX_MAPPING_ROWS]:
        lines.append(
            "| "
            f"`{binding.id}` | "
            f"`{binding.direction.value}` | "
            f"{_endpoint_display(binding.transformer_endpoint)} | "
            f"{_endpoint_display(binding.pipeline_endpoint)} | "
            f"{_literal_display(binding.literal)} | "
            f"`{_source_display(binding.source)}` |"
        )
    if len(bindings) > MAX_MAPPING_ROWS:
        omitted = len(bindings) - MAX_MAPPING_ROWS
        lines.append(f"| ... | ... | ... | ... | {omitted} additional bindings omitted | ... |")
    return "\n".join(lines) + "\n"


def _endpoint_display(endpoint: MappingEndpoint | None) -> str:
    if endpoint is None:
        return ""
    return f"`{_escape_table(endpoint.raw_path)}`"


def _literal_display(literal: LiteralValue | None) -> str:
    if literal is None:
        return ""
    if not literal.present:
        return "`not-present`"
    if literal.value is not None:
        return f"`{_escape_table(literal.value)}`"
    if literal.marker:
        return f"`{literal.marker}`"
    return f"`{literal.disclosure.value}`"


def _source_display(source: SourceReference) -> str:
    line = f":{source.line}" if source.line else ""
    return f"{source.path}{line}"


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


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
        label = _text_display(node.label)
        if label:
            detail_parts.append(label)
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


def _text_display(text: TextValue | None) -> str | None:
    if text is None:
        return None
    if text.value:
        return text.value
    if text.marker:
        return text.marker
    return None


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
