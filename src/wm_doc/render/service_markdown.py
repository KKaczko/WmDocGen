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
    JavaImport,
    JavaInvocationOccurrence,
    JavaPipelineAccess,
    JavaServiceAnalysis,
    JavaTypeReference,
    LiteralValue,
    MappingEndpoint,
    MappingOperation,
    ProcessDefinition,
    ProcessServiceMembership,
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
| Source service type | `{{ source_service_type }}` |
| Analysis support | `{{ service.analysis_status }}` |
| Description status | `{{ service.description_status }}` |
| Importance | `{{ service.classification.importance }}` |
| Layer | `{{ service.classification.layer }}` |
| Identity basis | `{{ service.identity.basis }}` |

## Analysis Support

{% if service.analysis_status.value == "OPAQUE" -%}
The artifact was identified as a service, but its implementation-specific format was not analyzed.
Only common service metadata is represented.
{% elif service.analysis_status.value == "PARTIAL" -%}
The artifact was identified as a service and supported metadata was extracted, but one or more
service-level findings describe unavailable or malformed evidence.
{% else -%}
The artifact was analyzed by the supported parser for its service type.
{% endif %}

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

{% if service.java_analysis %}
## Java Analysis

### Source Consistency

{{ render_java_source_consistency(service.java_analysis) }}

### Observed Pipeline Reads

{{ render_java_pipeline_accesses(java_reads) }}

### Observed Pipeline Writes

{{ render_java_pipeline_accesses(java_writes) }}

### Observed Pipeline Removes

{{ render_java_pipeline_accesses(java_removes) }}

### Static Integration Server Calls

{{ render_java_invocations(java_static_invocations) }}

### Dynamic Invocation Sites

{{ render_java_invocations(java_dynamic_invocations) }}

### Declared Imports

{{ render_java_imports(service.java_analysis.imports) }}

### Referenced Java Types

{{ render_java_types(service.java_analysis.referenced_types) }}
{% endif %}

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

## Called By

{{ render_incoming_dependencies(incoming_dependencies) }}

## Processes

{{ render_process_memberships(process_memberships, process_definitions) }}

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

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.
""",
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_service_markdown(
    service: FlowService,
    incoming_dependencies: list[UniqueDependency] | None = None,
    process_memberships: list[ProcessServiceMembership] | None = None,
    process_definitions: dict[str, ProcessDefinition] | None = None,
) -> str:
    incoming_dependencies = incoming_dependencies or []
    process_memberships = process_memberships or []
    process_definitions = process_definitions or {}
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
    java_reads = _java_accesses_for_kind(service.java_analysis, "READ")
    java_writes = _java_accesses_for_kind(service.java_analysis, "WRITE")
    java_removes = _java_accesses_for_kind(service.java_analysis, "REMOVE")
    java_static_invocations = _java_invocations_for_static(service.java_analysis, True)
    java_dynamic_invocations = _java_invocations_for_static(service.java_analysis, False)
    description_text = _text_display(service.description)
    return _TEMPLATE.render(
        service=service,
        description_text=description_text,
        source_service_type=service.source_service_type or "<not declared>",
        normal_dependencies=normal_dependencies,
        transformer_dependencies=transformer_dependencies,
        incoming_dependencies=incoming_dependencies,
        process_memberships=process_memberships,
        process_definitions=process_definitions,
        service_calls=service_calls,
        transformer_calls=transformer_calls,
        input_document_dependencies=input_document_dependencies,
        output_document_dependencies=output_document_dependencies,
        resolved_document_references=resolved_document_references,
        unresolved_document_references=unresolved_document_references,
        copy_operations=copy_operations,
        set_operations=set_operations,
        delete_operations=delete_operations,
        java_reads=java_reads,
        java_writes=java_writes,
        java_removes=java_removes,
        java_static_invocations=java_static_invocations,
        java_dynamic_invocations=java_dynamic_invocations,
        flow_outline=_flow_outline(service.flow_tree),
        flow_count=lambda name: service.metrics.flow_node_counts.get(name, 0),
        mapping_count=lambda name: service.metrics.mapping_operation_type_counts.get(name, 0),
        binding_count=lambda name: service.metrics.transformer_binding_direction_counts.get(
            name, 0
        ),
        render_fields=_render_fields,
        render_dependencies=_render_dependencies,
        render_incoming_dependencies=_render_incoming_dependencies,
        render_process_memberships=_render_process_memberships,
        render_document_usage=_render_document_usage,
        render_document_references=_render_document_references,
        render_calls=_render_calls,
        render_mapping_operations=_render_mapping_operations,
        render_transformer_bindings=_render_transformer_bindings,
        render_java_source_consistency=_render_java_source_consistency,
        render_java_pipeline_accesses=_render_java_pipeline_accesses,
        render_java_invocations=_render_java_invocations,
        render_java_imports=_render_java_imports,
        render_java_types=_render_java_types,
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


def _java_accesses_for_kind(
    java_analysis: JavaServiceAnalysis | None, access_kind: str
) -> list[JavaPipelineAccess]:
    if java_analysis is None:
        return []
    return [
        access
        for access in java_analysis.pipeline_accesses
        if access.access_kind.value == access_kind
    ]


def _java_invocations_for_static(
    java_analysis: JavaServiceAnalysis | None, static: bool
) -> list[JavaInvocationOccurrence]:
    if java_analysis is None:
        return []
    return [
        invocation
        for invocation in java_analysis.invocation_occurrences
        if (invocation.target_status.value == "STATIC_TARGET") == static
    ]


def _render_dependencies(dependencies: list[UniqueDependency]) -> str:
    if not dependencies:
        return "No static targets were extracted for this dependency kind.\n"
    lines = [
        "| Occurrences | Resolved | Target Type | Target Support | Target |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for dependency in dependencies:
        lines.append(
            "| "
            f"{dependency.occurrence_count} | "
            f"{dependency.resolved} | "
            f"`{dependency.target_type or 'UNKNOWN'}` | "
            f"`{dependency.target_analysis_status or 'UNKNOWN'}` | "
            f"`{dependency.target_service}` |"
        )
    return "\n".join(lines) + "\n"


def _render_incoming_dependencies(dependencies: list[UniqueDependency]) -> str:
    if not dependencies:
        return "No incoming static service calls target this service.\n"
    lines = [
        "| Occurrences | Resolved | Target Support | Source | Kind | Source sample |",
        "| ---: | --- | --- | --- | --- | --- |",
    ]
    for dependency in sorted(dependencies, key=_incoming_dependency_key):
        sample = dependency.source_samples[0] if dependency.source_samples else None
        sample_text = (
            sample.path + (f":{sample.line}" if sample.line else "") if sample else ""
        )
        lines.append(
            "| "
            f"{dependency.occurrence_count} | "
            f"{dependency.resolved} | "
            f"`{dependency.target_analysis_status or 'UNKNOWN'}` | "
            f"`{dependency.source_service}` | "
            f"`{dependency.dependency_kind}` | "
            f"`{sample_text}` |"
        )
    return "\n".join(lines) + "\n"


def _render_process_memberships(
    memberships: list[ProcessServiceMembership],
    process_definitions: dict[str, ProcessDefinition],
) -> str:
    if not memberships:
        return "This service is not part of any declared process.\n"
    lines = [
        "| Process | Membership | Depth | Link |",
        "| --- | --- | ---: | --- |",
    ]
    for membership in sorted(
        memberships,
        key=lambda item: (item.process_id.casefold(), item.minimum_depth, item.id),
    ):
        process = process_definitions.get(membership.process_id)
        name = process.name if process is not None else membership.process_id
        role = "entrypoint" if membership.entrypoint else "transitive"
        lines.append(
            "| "
            f"`{name}` | "
            f"`{role}` | "
            f"{membership.minimum_depth} | "
            f"[`{membership.process_id}`](../processes/{membership.process_id}.md) |"
        )
    return "\n".join(lines) + "\n"


def _incoming_dependency_key(dependency: UniqueDependency) -> tuple[str, str, str]:
    return (
        dependency.source_service.casefold(),
        dependency.dependency_kind.value,
        dependency.id,
    )


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
        "| Call | Resolved | Target Type | Target Support | Target | Source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for call in calls[:40]:
        line = f":{call.source.line}" if call.source.line else ""
        lines.append(
            "| "
            f"`{call.id}` | "
            f"{call.resolved} | "
            f"`{call.target_type or 'UNKNOWN'}` | "
            f"`{call.target_analysis_status or 'UNKNOWN'}` | "
            f"`{call.target}` | "
            f"`{call.source.path}{line}` |"
        )
    if len(calls) > 40:
        lines.append(
            f"| ... | ... | ... | ... | {len(calls) - 40} additional calls omitted | ... |"
        )
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


def _render_java_source_consistency(java_analysis: JavaServiceAnalysis) -> str:
    source_set = java_analysis.source_set
    lines = [
        "| Field | Value |",
        "| --- | --- |",
        f"| Status | `{source_set.status.value}` |",
        f"| Parser mode | `{source_set.parser_mode.value}` |",
        f"| Fragment kind | `{source_set.fragment_kind.value}` |",
        f"| Complete source | `{source_set.complete_source_path or ''}` |",
        f"| Fragment | `{source_set.fragment_path or ''}` |",
        f"| Class | `{source_set.matched_class or ''}` |",
        f"| Method | `{source_set.matched_method or ''}` |",
        f"| Token match | `{source_set.token_match}` |",
    ]
    if source_set.method_range is not None:
        method_range = source_set.method_range
        lines.append(
            "| Method range | "
            f"`{method_range.start_line}:{method_range.start_column}-"
            f"{method_range.end_line}:{method_range.end_column}` |"
        )
    return "\n".join(lines) + "\n"


def _render_java_pipeline_accesses(accesses: list[JavaPipelineAccess]) -> str:
    if not accesses:
        return "No Java pipeline accesses were extracted for this section.\n"
    lines = [
        "| Access | API | Key | Scope | Type | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for access in accesses[:MAX_MAPPING_ROWS]:
        lines.append(
            "| "
            f"`{access.id}` | "
            f"`{access.api_form}` | "
            f"`{_escape_table(access.field_key or '<dynamic>')}` | "
            f"`{access.cursor_scope.value}` | "
            f"`{access.evidenced_java_type or ''}` | "
            f"`{_source_display(access.source.primary)}` |"
        )
    if len(accesses) > MAX_MAPPING_ROWS:
        omitted = len(accesses) - MAX_MAPPING_ROWS
        lines.append(f"| ... | ... | ... | ... | ... | {omitted} omitted |")
    return "\n".join(lines) + "\n"


def _render_java_invocations(invocations: list[JavaInvocationOccurrence]) -> str:
    if not invocations:
        return "No Java Integration Server invocation sites were extracted for this section.\n"
    lines = [
        "| Invocation | API | Status | Target | Resolved | Evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for invocation in invocations[:MAX_MAPPING_ROWS]:
        lines.append(
            "| "
            f"`{invocation.id}` | "
            f"`{invocation.api_form}` | "
            f"`{invocation.target_status.value}` | "
            f"`{invocation.canonical_target or invocation.declared_target or ''}` | "
            f"{invocation.resolved} | "
            f"`{_source_display(invocation.source.primary)}` |"
        )
    if len(invocations) > MAX_MAPPING_ROWS:
        omitted = len(invocations) - MAX_MAPPING_ROWS
        lines.append(f"| ... | ... | ... | ... | ... | {omitted} omitted |")
    return "\n".join(lines) + "\n"


def _render_java_imports(imports: list[JavaImport]) -> str:
    if not imports:
        return "No Java imports were extracted.\n"
    lines = [
        "| Import | Provenance | Category | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for java_import in imports[:MAX_MAPPING_ROWS]:
        lines.append(
            "| "
            f"`{java_import.declaration}` | "
            f"`{java_import.provenance.value}` | "
            f"`{java_import.category.value}` | "
            f"`{_source_display(java_import.source)}` |"
        )
    if len(imports) > MAX_MAPPING_ROWS:
        lines.append(f"| ... | ... | ... | {len(imports) - MAX_MAPPING_ROWS} omitted |")
    return "\n".join(lines) + "\n"


def _render_java_types(references: list[JavaTypeReference]) -> str:
    if not references:
        return "No Java type references were extracted from the matched service method.\n"
    lines = [
        "| Type | Resolved Import | Category | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for reference in references[:MAX_MAPPING_ROWS]:
        lines.append(
            "| "
            f"`{reference.type_name}` | "
            f"`{reference.resolved_import or ''}` | "
            f"`{reference.category.value}` | "
            f"`{_source_display(reference.source.primary)}` |"
        )
    if len(references) > MAX_MAPPING_ROWS:
        lines.append(f"| ... | ... | ... | {len(references) - MAX_MAPPING_ROWS} omitted |")
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


def write_service_markdown(
    output_dir: Path,
    services: list[FlowService],
    process_memberships: list[ProcessServiceMembership] | None = None,
    processes: list[ProcessDefinition] | None = None,
) -> list[Path]:
    service_dir = output_dir / "services"
    service_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    incoming_dependencies = _incoming_dependencies_by_target(services)
    memberships_by_service = _process_memberships_by_service(process_memberships or [])
    process_definitions = {process.process_id: process for process in processes or []}
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
        path.write_text(
            render_service_markdown(
                service,
                incoming_dependencies.get(service.identity.full_name, []),
                memberships_by_service.get(service.identity.full_name, []),
                process_definitions,
            ),
            encoding="utf-8",
        )
        written.append(path)
    return written


def _incoming_dependencies_by_target(
    services: list[FlowService],
) -> dict[str, list[UniqueDependency]]:
    incoming: dict[str, list[UniqueDependency]] = {
        service.identity.full_name: [] for service in services
    }
    for service in services:
        for dependency in service.unique_dependencies:
            if dependency.target_service in incoming:
                incoming[dependency.target_service].append(dependency)
    return {
        target: sorted(dependencies, key=_incoming_dependency_key)
        for target, dependencies in incoming.items()
    }


def _process_memberships_by_service(
    memberships: list[ProcessServiceMembership],
) -> dict[str, list[ProcessServiceMembership]]:
    grouped: dict[str, list[ProcessServiceMembership]] = {}
    for membership in memberships:
        grouped.setdefault(membership.service, []).append(membership)
    return {
        service: sorted(items, key=lambda item: (item.process_id.casefold(), item.id))
        for service, items in grouped.items()
    }
