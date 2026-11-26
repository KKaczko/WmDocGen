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

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from wm_doc.adapters import operation_phrase, sql_objects_phrase
from wm_doc.analysis import _apply_free_text_policy, _xml_path
from wm_doc.builtins import builtin_effect, is_builtin_name
from wm_doc.config import AppConfig
from wm_doc.ir import (
    AdapterDetails,
    CaseLabelKind,
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
from wm_doc.jdbc_facts import KIND_LABELS, adapter_findings
from wm_doc.xmlsafe import XmlParseError, XmlSecurityError, parse_xml_file

if TYPE_CHECKING:
    from wm_doc.flow_logic import FlowLogic

MAX_LITERAL_CHARS = 80
MAX_COMMENT_CHARS = 160
MAX_SIGNATURE_CHILDREN = 8
MAX_JAVA_ITEMS = 12

# A callee annotation lookup: full service name -> one-line text, or None when unknown.
CalleeNotes = Callable[[str], str | None]
# A callee output lookup: full service name -> its declared output fields, or None.
CalleeOutputs = Callable[[str], str | None]
# A callee adapter lookup: full service name -> the decoded DynamicSQL/CustomSQL service.
CalleeAdapters = Callable[[str], FlowService | None]
INPUT_MAP_MODES = {"INPUT", "INVOKEINPUT"}
MAX_RETURNED_FIELDS = 8


@dataclass(frozen=True)
class PseudocodeDetail:
    """How much mapping detail to include; lowered when a prompt must shrink.

    `sql_chars` caps a JDBC adapter's own SQL template and `callee_sql_chars` the SQL of the
    adapters a service calls (None: no cap, 0: left out; the decoded statement stays).
    """

    max_copies_per_map: int = 6
    max_sets_per_map: int = 10
    include_comments: bool = True
    sql_chars: int | None = None
    callee_sql_chars: int | None = None


FULL_DETAIL = PseudocodeDetail()
REDUCED_DETAIL = PseudocodeDetail(
    max_copies_per_map=0, max_sets_per_map=4, sql_chars=8000, callee_sql_chars=2000
)
MINIMAL_DETAIL = PseudocodeDetail(
    max_copies_per_map=0, max_sets_per_map=0, sql_chars=2000, callee_sql_chars=0
)
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
    callee_outputs: CalleeOutputs | None = None,
    logic: FlowLogic | None = None,
    callee_adapters: CalleeAdapters | None = None,
) -> str:
    """Render one service as indented pseudo-code lines.

    `facts_text` is the deterministic usage and data-effects block (see
    :mod:`wm_doc.effects`); `external_note` names the declared external system of a call
    target outside the analysed packages; `callee_outputs` gives the declared outputs of a
    called service, shown as a `returns:` line because they land in the pipeline. With
    `logic` (the control model, `flow_logic`), BRANCHes, cases, calls and EXITs carry their
    ids (`[D1]`, `[D1.c2]`, `[C3]`, `[E1]`) and named LOOP and TRY blocks show their names,
    so a model can refer to them; without it the view is unchanged. `callee_adapters`
    adds, under each call of a decoded JDBC adapter service, its statement, which field of
    this call feeds each bind parameter and substitution, and its SQL (`detail` caps it).
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
        if service.disabled_steps:
            lines.append(
                f"disabled steps left out: {service.disabled_steps} (they never run)"
            )
        lines.append("steps:")
        renderer = _FlowRenderer(
            service,
            callee_note,
            comments,
            detail,
            external_note,
            callee_outputs,
            logic,
            callee_adapters,
        )
        for child in service.flow_tree.children:
            renderer.visit(child, 1, None)
        lines.extend(renderer.lines or ["  (no steps)"])
    elif service.service_type is ServiceType.JAVA:
        lines.extend(_java_lines(service, callee_note, external_note))
    elif service.service_type is ServiceType.OPAQUE and service.adapter is not None:
        lines.extend(_adapter_lines(service, detail))
    elif service.service_type is ServiceType.OPAQUE:
        source_type = service.source_service_type or "unknown"
        lines.append(
            f"implementation: not analysed (service type `{source_type}`); "
            "only the signature and description are known"
        )
    return "\n".join(lines)


def _adapter_lines(service: FlowService, detail: PseudocodeDetail) -> list[str]:
    details = service.adapter
    assert details is not None
    if details.jdbc is not None and details.jdbc.supported:
        return jdbc_prompt_lines(service, detail.sql_chars)
    lines = [
        "implementation: JDBC adapter service; one configured database operation, "
        "no FLOW steps; the SQL text is not analysed"
    ]
    if details.operation:
        lines.append(f"  template: {details.operation} ({operation_phrase(details)})")
    if details.tables:
        lines.append("  tables: " + ", ".join(f"`{table}`" for table in details.tables))
    if details.connection:
        lines.append(f"  connection: `{details.connection}`")
    return lines


def _sql_block(
    sql: TextValue | None, limit: int | None, indent: str, substitutions: bool
) -> list[str]:
    """The SQL template between markers, cut at `limit` characters (None: whole)."""
    if sql is None:
        return [f"{indent}SQL template: not configured"]
    if sql.disclosure is not TextDisclosure.INCLUDED or sql.value is None:
        withheld = f"withheld by the disclosure policy ({sql.length} characters)"
        return [f"{indent}SQL template: {withheld}"]
    if limit == 0:
        return []
    text = sql.value
    shown = text if limit is None else text[:limit]
    lines = [
        f"{indent}SQL template (exact text between the markers; `?` are JDBC bind parameters"
        + (", `${name}` are text substitutions" if substitutions else "")
        + "):",
        f"{indent}  <<<SQL",
    ]
    lines += [f"{indent}  {line}" for line in shown.splitlines() or [""]]
    lines.append(f"{indent}  SQL>>>")
    if len(shown) < len(text):
        lines.append(
            f"{indent}  (cut to fit the context window: {len(shown)} of {len(text)} characters)"
        )
    return lines


def jdbc_prompt_lines(service: FlowService, sql_chars: int | None = None) -> list[str]:
    """A decoded DynamicSQL/CustomSQL service for the model: configuration, SQL and findings."""
    details = service.adapter
    assert details is not None and details.jdbc is not None
    config = details.jdbc
    analysis = config.sql_analysis
    lines = [
        "implementation: JDBC adapter service; one configured SQL statement, no FLOW steps",
        f"  template: {config.template_kind} ({operation_phrase(details)})",
    ]
    if details.connection:
        lines.append(f"  connection: `{details.connection}`")
    lines += _sql_block(config.sql, sql_chars, "  ", bool(config.variables)) or [
        f"  SQL template: left out to fit the context window ({config.sql.length} characters)"
        if config.sql is not None
        else "  SQL template: not configured"
    ]
    if analysis is not None:
        lines.append("  statement: " + _statement_summary(details))
    for item in config.inputs:
        bind = (
            analysis.binds[item.position - 1]
            if analysis is not None and item.position <= len(analysis.binds)
            else None
        )
        compared = (
            f" -> {bind.operator} `{bind.column}`"
            if bind is not None and bind.column and bind.operator
            else (f" -> {bind.role}" if bind is not None and bind.role != "value" else "")
        )
        lines.append(
            f"  bind parameter {item.position} (`?`): input `{item.field or '?'}` "
            f"({item.field_type or 'type not set'}, {item.jdbc_type or 'JDBC type not set'})"
            f"{compared}"
        )
    placeholders = {item.name: item for item in analysis.placeholders} if analysis else {}
    for variable in config.variables:
        where = placeholders.get(variable.name)
        context = (
            f"; in the SQL: {', '.join(where.contexts)}"
            + (f" for `{where.column}`" if where.column else "")
            if where is not None
            else "; not found in the SQL"
        )
        lines.append(
            f"  text substitution `${{{variable.name}}}`: input `{variable.field or '?'}` "
            f"({variable.field_type or 'type not set'}), inserted into the SQL text{context}"
        )
    for item in config.outputs:
        lines.append(
            f"  output column {item.position}: `{item.field or '?'}` "
            f"({item.jdbc_type or 'JDBC type not set'}) -> `{item.result_field or '?'}` "
            f"({item.result_type or 'type not set'})"
        )
    if config.sql_output_field:
        lines.append(
            f"  technical output: `{config.sql_output_field}` (the statement as run)"
        )
    settings = []
    if config.max_rows is not None:
        no_limit = " (no limit set)" if config.max_rows in ("0", "") else ""
        settings.append(f"maximum rows {config.max_rows or '(empty)'}{no_limit}")
    if config.query_timeout is not None:
        settings.append(f"query timeout {config.query_timeout or '(empty)'}")
    if settings:
        lines.append("  settings: " + ", ".join(settings))
    findings = adapter_findings(service)
    if findings:
        lines.append("  findings:")
        lines += [f"    [{KIND_LABELS[item.kind]}] {item.text}" for item in findings]
    return lines


def _statement_summary(details: AdapterDetails) -> str:
    assert details.jdbc is not None and details.jdbc.sql_analysis is not None
    analysis = details.jdbc.sql_analysis
    parts = [analysis.statement or "OTHER"]
    objects = sql_objects_phrase(details)
    if objects:
        parts.append(objects)
    parts.append("WHERE: " + ("yes" if analysis.where else "no"))
    parts.append("ORDER BY: " + (analysis.order_by or "none"))
    if analysis.pagination:
        parts.append("pagination: " + ", ".join(analysis.pagination))
    if analysis.joins:
        parts.append(f"joins: {analysis.joins}")
    if analysis.group_by:
        parts.append("GROUP BY: yes")
    if analysis.set_operations:
        parts.append("set operations: " + ", ".join(analysis.set_operations))
    if analysis.status != "analysed":
        parts.append(f"read {analysis.status.replace('_', ' ')}: " + "; ".join(analysis.notes))
    return "; ".join(parts)


def call_inputs(service: FlowService, call_id: str) -> dict[str, tuple[str, str]]:
    """Input fields the input map of one call sets or copies: path -> (display, how known).

    Paths are written without the leading slash and compared without case (`a/b`). Only the
    call's own input map is read: a field it does not set comes from the pipeline as it is
    when the call starts.
    """
    map_ids = {
        flow_map.id
        for flow_map in service.flow_maps
        if flow_map.parent_call_occurrence_id == call_id
        and (flow_map.mode or "").upper() in INPUT_MAP_MODES
    }
    values: dict[str, tuple[str, str]] = {}
    operations: Iterable[MappingOperation] = sorted(
        (op for op in service.mapping_operations if op.flow_map_id in map_ids),
        key=lambda op: op.map_operation_order,
    )
    for operation in operations:
        target = clean_pipeline_path(
            operation.target_endpoint.raw_path if operation.target_endpoint else None
        )
        if not target:
            continue
        segments = [segment for segment in target.split("/") if segment]
        if not segments:
            continue
        field = "/".join(segments).casefold()
        if operation.operation_type is MappingOperationType.SET:
            literal = operation.literal
            if literal is None or not literal.present or literal.is_null_like:
                values[field] = ("(empty)", "literal")
            elif literal.disclosure is LiteralDisclosure.INCLUDED and literal.value is not None:
                values[field] = (f"`{_short_literal(literal.value)}`", "literal")
            else:
                values[field] = ("(value withheld)", "literal")
        elif operation.operation_type is MappingOperationType.COPY:
            source = clean_pipeline_path(
                operation.source_endpoint.raw_path if operation.source_endpoint else None
            )
            if source:
                values.setdefault(field, (f"from `{source}`", "mapped from pipeline"))
    return values


def _short_literal(text: str, limit: int = 120) -> str:
    flat = " ".join(text.split()).replace("`", "'")
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."


def callee_adapters_lookup(services: Mapping[str, FlowService]) -> CalleeAdapters:
    """Decoded DynamicSQL/CustomSQL adapter services by name, for the lines under calls."""

    def adapter(target: str) -> FlowService | None:
        callee = services.get(target)
        details = callee.adapter if callee is not None else None
        if details is None or details.jdbc is None or not details.jdbc.supported:
            return None
        return callee

    return adapter


def adapter_call_lines(
    caller: FlowService, call_id: str | None, adapter: FlowService, sql_chars: int | None
) -> list[str]:
    """Under a call of a JDBC adapter: its statement, what this call feeds into it, its SQL."""
    details = adapter.adapter
    assert details is not None and details.jdbc is not None
    config = details.jdbc
    analysis = config.sql_analysis
    given = call_inputs(caller, call_id) if call_id is not None else {}
    record = config.input_record

    def fed(field: str | None) -> str:
        if field is None:
            return "input not configured"
        path = f"{record}/{field}" if record else field
        found = given.get(path.casefold())
        source = found[0] if found is not None else "not set in this call's input map"
        return f"input `{path}` <- {source}"

    head = f"{config.template_kind} runs {analysis.statement if analysis else 'SQL'}"
    objects = sql_objects_phrase(details)
    lines = [f"jdbc: {head}" + (f" {objects}" if objects else "")]
    binds = analysis.binds if analysis is not None else []
    for item in config.inputs:
        bind = binds[item.position - 1] if item.position <= len(binds) else None
        meets = (
            f" ({bind.operator} `{bind.column}`)"
            if bind is not None and bind.column and bind.operator
            else (f" ({bind.role})" if bind is not None and bind.role != "value" else "")
        )
        lines.append(f"  bind ?{item.position}{meets}: {fed(item.field)}")
    placeholders = {item.name: item for item in analysis.placeholders} if analysis else {}
    for variable in config.variables:
        where = placeholders.get(variable.name)
        context = (
            f" ({', '.join(where.contexts)}"
            + (f" for `{where.column}`" if where.column else "")
            + ")"
            if where is not None
            else ""
        )
        lines.append(f"  text substitution `${{{variable.name}}}`{context}: {fed(variable.field)}")
    results = [f"`{item.result_field}`" for item in config.outputs if item.result_field]
    if results:
        lines.append("  rows returned in " + ", ".join(results))
    lines += _sql_block(config.sql, sql_chars, "  ", bool(config.variables))
    return lines


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
        callee_outputs: CalleeOutputs | None = None,
        logic: FlowLogic | None = None,
        callee_adapters: CalleeAdapters | None = None,
    ) -> None:
        self.service = service
        self.callee_adapters = callee_adapters
        self.annotate = logic is not None
        self.ids: dict[str, str] = {}
        if logic is not None:
            for decision in logic.decisions:
                self.ids[decision.node_id] = decision.id
                for item in decision.cases:
                    self.ids[item.node_id] = item.id
            self.ids.update({call.node_id: call.id for call in logic.calls})
            self.ids.update({item.node_id: item.id for item in logic.exits})
        self.callee_note = callee_note
        self.external_note = external_note
        self.callee_outputs = callee_outputs
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

    def tag(self, node: FlowNode) -> str:
        found = self.ids.get(node.id)
        return f"[{found}] " if found else ""

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
            label = _text(node.label) if self.annotate else None
            named = f"LOOP {_quote(label)}" if label else "LOOP"
            text = f"{named} over {_path(node.in_array) or '?'}"
            if node.out_array:
                text += f" collecting {_path(node.out_array)}"
            self.emit(depth, text, node)
            self._children(node, depth + 1)
        elif kind is FlowNodeType.REPEAT:
            self.emit(depth, _repeat_text(node), node)
            self._children(node, depth + 1)
        elif kind is FlowNodeType.EXIT:
            self.emit(depth, self.tag(node) + _exit_text(node), node)
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
            block = f"{form} {_quote(label)}" if self.annotate and label else form
            self.emit(depth, f"{block}:", node)
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
        head = f"BRANCH on {switch}:" if switch else "BRANCH:"
        self.emit(depth, self.tag(node) + head, node)
        for case in node.children:
            if case.type is not FlowNodeType.BRANCH_CASE:
                self.visit(case, depth + 1, None)
                continue
            label = _text(case.label)
            withheld = label is None and case.label is not None
            if case.is_default_case or label == "$default":
                head = "otherwise:"
            elif label == "$null" or (withheld and case.case_kind is CaseLabelKind.NULL):
                head = "when missing:" if switch else "when (empty condition):"
            elif withheld:
                kind = (
                    "expression"
                    if node.evaluate_labels
                    else _WITHHELD_KINDS.get(case.case_kind, "label")
                )
                head = f"when ({kind} withheld):"
            elif switch:
                head = f"when {_quote(label)}:"
            else:
                head = f"when {label}:" if label else "when (no condition):"
            self.emit(depth + 1, self.tag(case) + head)
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
        self.emit(depth, f"{self.tag(node)}{verb} {target}  # {note}", node)
        returned = self.callee_outputs(target) if self.callee_outputs is not None else None
        for child in node.children:
            if child.type is FlowNodeType.MAP:
                if returned and self._is_output_map(child):
                    self.emit(depth + 1, f"returns: {returned}")
                    returned = None
                self._map(child, depth + 1, header=False)
            else:
                self.visit(child, depth + 1, None)
        if returned:
            self.emit(depth + 1, f"returns: {returned}")
        adapter = (
            self.callee_adapters(target)
            if self.callee_adapters is not None and node.type is FlowNodeType.INVOKE
            else None
        )
        if adapter is not None:
            for line in adapter_call_lines(
                self.service, node.call_occurrence_id, adapter, self.detail.callee_sql_chars
            ):
                self.emit(depth + 1, line)

    def _is_output_map(self, node: FlowNode) -> bool:
        flow_map = self.maps.get(node.structural_path)
        mode = (flow_map.mode if flow_map else node.attributes.get("MODE")) or ""
        return mode.upper() in {"OUTPUT", "INVOKEOUTPUT"}

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


def callee_outputs_lookup(services: Mapping[str, FlowService]) -> CalleeOutputs:
    """Declared outputs of analysed services, for `returns:` lines after their calls."""

    def outputs(target: str) -> str | None:
        callee = services.get(target)
        if callee is None or not callee.signature.outputs:
            return None
        fields = callee.signature.outputs
        shown = ", ".join(_field_text(field) for field in fields[:MAX_RETURNED_FIELDS])
        extra = len(fields) - MAX_RETURNED_FIELDS
        return shown + (f", and {extra} more" if extra > 0 else "")

    return outputs


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


_WITHHELD_KINDS: dict[CaseLabelKind | None, str] = {
    CaseLabelKind.TEXT: "value",
    CaseLabelKind.PATTERN: "pattern",
}


def _exit_text(node: FlowNode) -> str:
    if node.exit_label is not None:
        label = _text(node.exit_label)
        scope_text = _quote(label) if label is not None else "a labelled step (label withheld)"
    else:
        scope = node.exit_from or "$parent"
        scope_text = {
            "$loop": "the loop",
            "$parent": "the parent step",
            "$flow": "the service",
        }.get(scope, _quote(scope))
    signal = (node.signal or "SUCCESS").upper()
    text = f"EXIT {scope_text} with {signal.lower()}"
    if signal == "FAILURE" and node.failure_message is not None:
        message = _text(node.failure_message)
        text += (
            f" message {_quote(_one_line(message, MAX_LITERAL_CHARS))}"
            if message is not None
            else " message (withheld)"
        )
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
