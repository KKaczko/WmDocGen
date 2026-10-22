"""Compact pseudo-code view of one analysed service, written for a language model.

The view restates facts already in ``analysis.v9`` -- the signature, the ordered FLOW
tree, mapping literals and copies, transformer calls, Java pipeline accesses -- in a
short indented form that a small local model reads far more reliably than JSON
evidence records. Each call line can carry an annotation: a platform effect label,
"outside the analysed packages", or the one-line AI summary already produced for the callee.

Developer step comments (``<COMMENT>`` children in ``flow.xml``) are not part of the
canonical snapshot. They are read here directly from the package file, matched to
FLOW nodes by XML path, and filtered through the free-text disclosure policy.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from wm_doc.analysis import _apply_free_text_policy, _xml_path
from wm_doc.builtins import builtin_effect, is_builtin_name
from wm_doc.config import AppConfig
from wm_doc.ir import (
    FlowNode,
    FlowNodeType,
    FlowService,
    LiteralDisclosure,
    MappingEndpoint,
    MappingOperation,
    MappingOperationType,
    ServiceType,
    SignatureField,
    SignatureOrigin,
    SourceReference,
    TextDisclosure,
    TextValue,
)
from wm_doc.xmlsafe import XmlParseError, XmlSecurityError, parse_xml_file

MAX_LITERAL_CHARS = 80
MAX_COMMENT_CHARS = 160
MAX_SIGNATURE_CHILDREN = 8
MAX_JAVA_ITEMS = 12

# A callee annotation lookup: full service name -> one-line text, or None when unknown.
CalleeNotes = Callable[[str], str | None]


@dataclass(frozen=True)
class PseudocodeDetail:
    """How much mapping detail to include; lowered when a prompt must shrink."""

    max_copies_per_map: int = 6
    max_sets_per_map: int = 10
    include_comments: bool = True


FULL_DETAIL = PseudocodeDetail()
REDUCED_DETAIL = PseudocodeDetail(max_copies_per_map=0, max_sets_per_map=4)
MINIMAL_DETAIL = PseudocodeDetail(max_copies_per_map=0, max_sets_per_map=0)
# Tried in order until the prompt fits the model's context window.
DETAIL_LADDER = (FULL_DETAIL, REDUCED_DETAIL, MINIMAL_DETAIL)


def render_pseudocode(
    service: FlowService,
    callee_note: CalleeNotes,
    *,
    comments: Mapping[str, str] | None = None,
    detail: PseudocodeDetail = FULL_DETAIL,
    facts_text: str | None = None,
    external_note: CalleeNotes | None = None,
) -> str:
    """Render one service as indented pseudo-code lines.

    `facts_text` is the deterministic usage and data-effects block (see
    :mod:`wm_doc.effects`); `external_note` names the declared external system of a call
    target outside the analysed packages.
    """
    comments = comments if detail.include_comments and comments else {}
    lines = [f"service {service.identity.full_name}  [{service.service_type.value}]"]
    description = _text(service.description)
    if description:
        lines.append(f"developer description: {_one_line(description, 400)}")
    if service.signature_origin is SignatureOrigin.SPECIFICATION:
        lines.append(f"signature: from specification {service.specification}")
    lines.extend(_signature_lines("inputs", service.signature.inputs))
    lines.extend(_signature_lines("outputs", service.signature.outputs))
    if facts_text:
        lines.append(facts_text)
    if service.service_type is ServiceType.FLOW and service.flow_tree is not None:
        lines.append("steps:")
        renderer = _FlowRenderer(service, callee_note, comments, detail, external_note)
        for child in service.flow_tree.children:
            renderer.visit(child, 1, None)
        lines.extend(renderer.lines or ["  (no steps)"])
    elif service.service_type is ServiceType.JAVA:
        lines.extend(_java_lines(service, callee_note, external_note))
    elif service.service_type is ServiceType.OPAQUE:
        source_type = service.source_service_type or "unknown"
        lines.append(
            f"implementation: not analysed (service type `{source_type}`); "
            "only the signature and description are known"
        )
    return "\n".join(lines)


def call_annotation(
    target: str,
    resolved: bool,
    callee_note: CalleeNotes,
    external_note: CalleeNotes | None = None,
) -> str:
    """Describe a call target for the model without guessing."""
    effect = builtin_effect(target)
    if effect is not None:
        return f"platform: {effect.label}"
    if is_builtin_name(target):
        return "platform service"
    if not resolved:
        system = external_note(target) if external_note is not None else None
        if system:
            return f"outside the analysed packages; declared external system {system}"
        return "outside the analysed packages"
    note = callee_note(target)
    return note if note else "no description available"


def load_flow_comments(
    scan_root: Path, service: FlowService, config: AppConfig
) -> dict[str, str]:
    """Return step comments keyed by the XML path of the step they belong to."""
    if service.service_type is not ServiceType.FLOW or service.flow_tree is None:
        return {}
    relative = service.flow_tree.source.path
    flow_path = (scan_root / relative).resolve()
    try:
        flow_path.relative_to(scan_root.resolve())
    except ValueError:
        return {}
    if not flow_path.is_file():
        return {}
    try:
        root = parse_xml_file(flow_path)
    except (XmlParseError, XmlSecurityError, OSError):
        return {}
    comments: dict[str, str] = {}
    for element in root.iter("COMMENT"):
        parent = element.getparent()
        # Designer comments are often framed as "-- Try / Catch --"; the dashes carry nothing.
        text = " ".join((element.text or "").split()).strip("-= ")
        if parent is None or not text:
            continue
        source = SourceReference(path=relative, artifact_type="comment")
        policy = _apply_free_text_policy(text, "flow_step_comment", source, config)
        if policy is None or policy.disclosure is not TextDisclosure.INCLUDED:
            continue
        if policy.value:
            comments[_xml_path(parent)] = _one_line(policy.value, MAX_COMMENT_CHARS)
    return comments


class _FlowRenderer:
    def __init__(
        self,
        service: FlowService,
        callee_note: CalleeNotes,
        comments: Mapping[str, str],
        detail: PseudocodeDetail,
        external_note: CalleeNotes | None = None,
    ) -> None:
        self.service = service
        self.callee_note = callee_note
        self.external_note = external_note
        self.comments = comments
        self.detail = detail
        self.lines: list[str] = []
        self.resolved = {
            dependency.target_service: dependency.resolved
            for dependency in service.unique_dependencies
        }
        self.maps = {flow_map.structural_path: flow_map for flow_map in service.flow_maps}
        operations: dict[str, list[MappingOperation]] = {}
        for operation in service.mapping_operations:
            operations.setdefault(operation.flow_map_id, []).append(operation)
        for items in operations.values():
            items.sort(key=lambda item: item.map_operation_order)
        self.operations = operations

    def emit(self, depth: int, text: str, node: FlowNode | None = None) -> None:
        comment = self.comments.get(node.source.xml_path or "") if node is not None else None
        suffix = f"  // {comment}" if comment else ""
        self.lines.append("  " * depth + text + suffix)

    def visit(self, node: FlowNode, depth: int, case_label: str | None) -> None:
        kind = node.type
        if kind is FlowNodeType.SEQUENCE:
            self._sequence(node, depth, case_label)
        elif kind is FlowNodeType.BRANCH:
            self._branch(node, depth)
        elif kind is FlowNodeType.LOOP:
            text = f"LOOP over {_path(node.in_array) or '?'}"
            if node.out_array:
                text += f" collecting {_path(node.out_array)}"
            self.emit(depth, text, node)
            self._children(node, depth + 1)
        elif kind is FlowNodeType.REPEAT:
            self.emit(depth, _repeat_text(node), node)
            self._children(node, depth + 1)
        elif kind is FlowNodeType.EXIT:
            self.emit(depth, _exit_text(node), node)
        elif kind in (FlowNodeType.INVOKE, FlowNodeType.MAPINVOKE):
            self._call(node, depth)
        elif kind is FlowNodeType.MAP:
            self._map(node, depth, header=True)
        else:
            self._children(node, depth)

    def _children(self, node: FlowNode, depth: int, case_label: str | None = None) -> None:
        for child in node.children:
            self.visit(child, depth, case_label)

    def _sequence(self, node: FlowNode, depth: int, case_label: str | None) -> None:
        label = _text(node.label)
        form = (node.form or "").upper()
        if form in {"TRY", "CATCH", "FINALLY"}:
            self.emit(depth, f"{form}:", node)
            self._children(node, depth + 1)
            return
        exit_on = (node.exit_on or "FAILURE").upper()
        named = label is not None and label != case_label
        if exit_on == "SUCCESS":
            title = f"SEQUENCE {_quote(label)} " if named else "SEQUENCE "
            self.emit(depth, title + "(stops at the first child that succeeds)", node)
            self._children(node, depth + 1)
        elif exit_on == "DONE":
            title = f"SEQUENCE {_quote(label)} " if named else "SEQUENCE "
            self.emit(depth, title + "(runs every child, ignoring failures)", node)
            self._children(node, depth + 1)
        elif named:
            self.emit(depth, f"SEQUENCE {_quote(label)}:", node)
            self._children(node, depth + 1)
        else:
            # A plain sequence adds no meaning for a reader; keep its children in place.
            if node.source.xml_path in self.comments:
                self.emit(depth, "SEQUENCE:", node)
                self._children(node, depth + 1)
            else:
                self._children(node, depth)

    def _branch(self, node: FlowNode, depth: int) -> None:
        switch = _path(node.switch)
        self.emit(depth, f"BRANCH on {switch}:" if switch else "BRANCH:", node)
        for case in node.children:
            if case.type is not FlowNodeType.BRANCH_CASE:
                self.visit(case, depth + 1, None)
                continue
            label = _text(case.label)
            if case.is_default_case or label == "$default":
                head = "otherwise:"
            elif label == "$null":
                head = "when missing:" if switch else "when (empty condition):"
            elif switch:
                head = f"when {_quote(label)}:"
            else:
                head = f"when {label}:" if label else "when (no condition):"
            self.emit(depth + 1, head)
            before = len(self.lines)
            self._children(case, depth + 2, label)
            if len(self.lines) == before:
                self.emit(depth + 2, "(nothing)")

    def _call(self, node: FlowNode, depth: int) -> None:
        target = node.target or "?"
        verb = "CALL" if node.type is FlowNodeType.INVOKE else "TRANSFORM via"
        note = call_annotation(
            target, self.resolved.get(target, False), self.callee_note, self.external_note
        )
        self.emit(depth, f"{verb} {target}  # {note}", node)
        for child in node.children:
            if child.type is FlowNodeType.MAP:
                self._map(child, depth + 1, header=False)
            else:
                self.visit(child, depth + 1, None)

    def _map(self, node: FlowNode, depth: int, *, header: bool) -> None:
        flow_map = self.maps.get(node.structural_path)
        mode = (flow_map.mode if flow_map else node.attributes.get("MODE")) or ""
        direction = {"INPUT": "in", "INVOKEINPUT": "in", "OUTPUT": "out", "INVOKEOUTPUT": "out"}
        prefix = direction.get(mode.upper(), "")
        operations = self.operations.get(flow_map.id, []) if flow_map else []
        sets = [op for op in operations if op.operation_type is MappingOperationType.SET]
        copies = [op for op in operations if op.operation_type is MappingOperationType.COPY]
        body: list[str] = []
        for operation in sets[: self.detail.max_sets_per_map]:
            body.append(f"set {_endpoint(operation.target_endpoint)} = {_literal(operation)}")
        for operation in copies[: self.detail.max_copies_per_map]:
            body.append(
                f"copy {_endpoint(operation.source_endpoint)} -> "
                f"{_endpoint(operation.target_endpoint)}"
            )
        hidden = (len(sets) - min(len(sets), self.detail.max_sets_per_map)) + (
            len(copies) - min(len(copies), self.detail.max_copies_per_map)
        )
        if hidden:
            body.append(f"... {hidden} more mapping(s)")
        transformers = [child for child in node.children if child.type is FlowNodeType.MAPINVOKE]
        if header:
            if not body and not transformers:
                if node.source.xml_path in self.comments:
                    self.emit(depth, "MAP", node)
                return
            self.emit(depth, "MAP:", node)
            inner = depth + 1
        else:
            inner = depth
        for line in body:
            self.emit(inner, f"{prefix}: {line}" if prefix else line)
        for child in transformers:
            self._call(child, inner)


def _signature_lines(label: str, fields: list[SignatureField]) -> list[str]:
    if not fields:
        return [f"{label}: (none declared)"]
    lines = [f"{label}:"]
    for field in fields:
        lines.append(f"  {_field_text(field)}")
        for child in field.children[:MAX_SIGNATURE_CHILDREN]:
            lines.append(f"    {_field_text(child)}")
        if len(field.children) > MAX_SIGNATURE_CHILDREN:
            lines.append(f"    ... {len(field.children) - MAX_SIGNATURE_CHILDREN} more field(s)")
    return lines


def _field_text(field: SignatureField) -> str:
    kind = field.data_type or "unknown"
    if field.document_reference:
        kind = f"document {field.document_reference}"
    if field.dimensions:
        kind += " list" if field.dimensions == 1 else f" list[{field.dimensions}]"
    optional = " (optional)" if field.optional else ""
    return f"{field.name}: {kind}{optional}"


def _java_lines(
    service: FlowService, callee_note: CalleeNotes, external_note: CalleeNotes | None = None
) -> list[str]:
    analysis = service.java_analysis
    if analysis is None:
        return ["implementation: Java (no source evidence available)"]
    lines = ["implementation: Java"]
    grouped: dict[str, list[str]] = {"READ": [], "WRITE": [], "REMOVE": []}
    for access in analysis.pipeline_accesses:
        key = access.field_key if access.field_key and not access.dynamic_key else "(dynamic)"
        bucket = grouped.setdefault(access.access_kind.value, [])
        if key not in bucket:
            bucket.append(key)
    for kind, verb in (("READ", "reads"), ("WRITE", "writes"), ("REMOVE", "removes")):
        if grouped.get(kind):
            lines.append(f"  {verb} pipeline fields: {', '.join(grouped[kind][:MAX_JAVA_ITEMS])}")
    for invocation in analysis.invocation_occurrences:
        target = invocation.canonical_target or invocation.declared_target
        if target:
            note = call_annotation(target, invocation.resolved, callee_note, external_note)
            lines.append(f"  CALL {target}  # {note}")
        else:
            lines.append("  CALL (target computed at runtime)")
    types = sorted({reference.type_name for reference in analysis.referenced_types})
    if types:
        shown = ", ".join(types[:MAX_JAVA_ITEMS])
        extra = len(types) - min(len(types), MAX_JAVA_ITEMS)
        lines.append(f"  uses Java types: {shown}" + (f" and {extra} more" if extra else ""))
    lines.append("  (Java control flow and error handling are not analysed)")
    return lines


def _repeat_text(node: FlowNode) -> str:
    count = (node.attributes.get("COUNT") or "").strip()
    loop_on = (node.attributes.get("LOOP-ON") or "FAILURE").strip().lower()
    back_off = (node.attributes.get("BACK-OFF") or "").strip()
    times = "repeatedly" if count in {"", "-1"} else f"up to {count} more time(s)"
    text = f"REPEAT {times} on {loop_on}"
    if back_off and back_off != "0":
        text += f", waiting {back_off}s between attempts"
    return text + ":"


def _exit_text(node: FlowNode) -> str:
    scope = node.exit_from or "$parent"
    scope_text = {"$loop": "the loop", "$parent": "the parent step", "$flow": "the service"}.get(
        scope, _quote(scope)
    )
    signal = (node.signal or "SUCCESS").upper()
    text = f"EXIT {scope_text} with {signal.lower()}"
    if signal == "FAILURE" and node.failure_message:
        text += f" message {_quote(_one_line(node.failure_message, MAX_LITERAL_CHARS))}"
    return text


def _endpoint(endpoint: MappingEndpoint | None) -> str:
    if endpoint is None:
        return "?"
    return _path(endpoint.raw_path) or "?"


def _path(raw: str | None) -> str | None:
    """Strip webMethods type suffixes: ``/key;4;0;doc:Type/userId;1;0`` -> ``/key/userId``."""
    if not raw:
        return None
    parts = [segment.split(";", 1)[0] for segment in raw.split("/")]
    return "/".join(parts)


def _literal(operation: MappingOperation) -> str:
    literal = operation.literal
    if literal is None or not literal.present:
        return "(no value)"
    if literal.disclosure is not LiteralDisclosure.INCLUDED:
        return "(value withheld)"
    if literal.is_null_like or literal.value is None:
        return "(empty)"
    return _quote(_one_line(literal.value, MAX_LITERAL_CHARS))


def _text(value: TextValue | None) -> str | None:
    if value is None or value.disclosure is not TextDisclosure.INCLUDED or not value.value:
        return None
    return value.value


def _quote(value: str | None) -> str:
    return f'"{value}"' if value is not None else '""'


def clean_pipeline_path(raw: str | None) -> str | None:
    """Public form of the path cleaner, shared with the effects analysis."""
    return _path(raw)


def literal_display(operation: MappingOperation) -> str:
    """Public form of the literal display, shared with the effects analysis."""
    return _literal(operation)


def _one_line(text: str, limit: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."
