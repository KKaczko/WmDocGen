"""Findings about JDBC adapter services and the calls that reach them (derived on demand).

From the decoded configuration (`AdapterDetails.jdbc`), its SQL reading (`sql_analysis.py`)
and the service signature, and for each direct FLOW caller from the call's own input map
and the steps around it. Nothing is stored in `analysis.json`, nothing is inferred from
names, and every finding says what it is:

- `fact`: read from the configuration or the signature;
- `inferred`: follows from facts by a stated rule (DynamicSQL puts the text of a variable
  into the statement; JDBC binds each `?` in order);
- `risk`: a potential problem the facts allow but do not prove (never a confirmed
  vulnerability);
- `unknown`: depends on values only known at run time.

Callers are read the way `effects.py` reads platform calls: what the call's input map sets
or copies is observed; a field it does not set comes from the pipeline as it is when the call
starts (its earlier origins are what `flow_lineage` shows). A call inside a LOOP runs once per
item; whether that is one query per row of an earlier query (N+1) depends on the data and
is a risk, not a fact.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

from wm_doc.ir import (
    CallType,
    FlowNode,
    FlowNodeType,
    FlowService,
    JdbcServiceConfig,
    SignatureField,
    TextDisclosure,
)

CONNECTION_OVERRIDE_FIELD = "$connectionName"
CREDENTIALS_OVERRIDE_RECORD = "overrideCredentials"
MAX_CALLERS = 50
MAX_USES = 200
MAX_CALLER_LINES = 20

# What one call's input map sets or copies: (service, call id) -> {path: (display, how)}.
# `effects.call_inputs` (passed in, so this module stays below effects and pseudocode).
CallInputs = Callable[[FlowService, str], dict[str, tuple[str, str]]]

FACT = "fact"
INFERRED = "inferred"
RISK = "risk"
UNKNOWN = "unknown"
KIND_LABELS = {
    FACT: "fact",
    INFERRED: "inferred",
    RISK: "potential risk",
    UNKNOWN: "unknown at run time",
}


@dataclass(frozen=True)
class JdbcFinding:
    kind: str  # fact, inferred, risk or unknown
    code: str
    text: str
    basis: str


@dataclass(frozen=True)
class FieldPass:
    """What one call's input map gives one adapter input."""

    path: str  # as the adapter's signature names it, `record/field`
    role: str  # substitution or connection override
    display: str | None  # `literal`, from `/path`, (value withheld); None: not set by the map
    how: str  # literal, mapped from pipeline, or not set in the call's input map


@dataclass(frozen=True)
class AdapterUse:
    """One call of a JDBC adapter service by a FLOW service."""

    caller: str
    call_id: str
    adapter: str
    loops: tuple[str, ...]  # enclosing LOOP / REPEAT steps, outermost first
    passes: tuple[FieldPass, ...]


def jdbc_config(service: FlowService) -> JdbcServiceConfig | None:
    adapter = service.adapter
    return adapter.jdbc if adapter is not None else None


def input_fields(service: FlowService) -> list[SignatureField]:
    """The fields of the adapter's input record (`<template>Input`), or the inputs."""
    config = jdbc_config(service)
    record = config.input_record if config is not None else None
    for field in service.signature.inputs:
        if record and field.name == record and field.children:
            return field.children
    return list(service.signature.inputs)


def has_input(service: FlowService, name: str) -> bool:
    return any(field.name == name for field in service.signature.inputs) or any(
        field.name == name for field in input_fields(service)
    )


def adapter_findings(service: FlowService) -> list[JdbcFinding]:
    """Findings from one adapter service's own configuration and signature."""
    config = jdbc_config(service)
    if config is None or not config.supported:
        return []
    found: list[JdbcFinding] = []
    sql = config.sql
    if sql is not None and sql.disclosure is not TextDisclosure.INCLUDED:
        found.append(
            JdbcFinding(
                FACT,
                "sql-withheld",
                "The SQL text is withheld by the free-text policy or the secret guard; the "
                "facts below were read from it before it was withheld.",
                "free-text policy",
            )
        )
    found += _substitution_findings(config)
    found += _binding_findings(config)
    found += _signature_findings(service, config)
    if config.sql_analysis is not None:
        found += _statement_findings(config)
    if has_input(service, CONNECTION_OVERRIDE_FIELD):
        configured = service.adapter.connection if service.adapter is not None else None
        default = f"`{configured}` is the configured one" if configured else "none is configured"
        found.append(
            JdbcFinding(
                FACT,
                "connection-override",
                f"Callers can choose another JDBC connection at run time through "
                f"`{CONNECTION_OVERRIDE_FIELD}`; {default}.",
                "input signature",
            )
        )
    if has_input(service, CREDENTIALS_OVERRIDE_RECORD):
        found.append(
            JdbcFinding(
                FACT,
                "credentials-override",
                f"Callers can pass other database credentials at run time through "
                f"`{CREDENTIALS_OVERRIDE_RECORD}` (its values are never read).",
                "input signature",
            )
        )
    if config.sql_output_field:
        found.append(
            JdbcFinding(
                FACT,
                "statement-output",
                f"The statement as run (after substitution) is returned in "
                f"`{config.sql_output_field}`, a technical output; the rows are in "
                f"{_result_fields(config)}.",
                "sqlOutputField",
            )
        )
    return found


def _result_fields(config: JdbcServiceConfig) -> str:
    fields = [item.result_field for item in config.outputs if item.result_field]
    return ", ".join(f"`{name}`" for name in fields) if fields else "no configured output"


def _substitution_findings(config: JdbcServiceConfig) -> list[JdbcFinding]:
    found: list[JdbcFinding] = []
    analysis = config.sql_analysis
    used = {item.name for item in analysis.placeholders} if analysis is not None else set()
    declared = {variable.name for variable in config.variables}
    for variable in config.variables:
        target = f" (input `{variable.field}`)" if variable.field else ""
        found.append(
            JdbcFinding(
                INFERRED,
                "text-substitution",
                f"`${{{variable.name}}}` is replaced by the text of its input{target} before "
                "the statement runs: it is part of the SQL, not a bind parameter.",
                "DynamicSQL variable (sqlVariables, sqlInputFields)",
            )
        )
        found.append(
            JdbcFinding(
                RISK,
                "sql-injection-exposure",
                f"Potential SQL injection exposure: whatever reaches `${{{variable.name}}}` "
                "becomes SQL text, so it must be validated or built by trusted code. Not "
                "confirmed: it depends on where callers take the value from.",
                "DynamicSQL text substitution",
            )
        )
    for name in sorted(used - declared):
        found.append(
            JdbcFinding(
                FACT,
                "undeclared-substitution",
                f"The SQL contains `${{{name}}}`, which is not a configured variable.",
                "sql, sqlVariables",
            )
        )
    if analysis is not None:
        for name in sorted(declared - used):
            found.append(
                JdbcFinding(
                    FACT,
                    "unused-variable",
                    f"The variable `{name}` is configured but `${{{name}}}` is not in the SQL.",
                    "sql, sqlVariables",
                )
            )
    return found


def _binding_findings(config: JdbcServiceConfig) -> list[JdbcFinding]:
    analysis = config.sql_analysis
    if analysis is None or analysis.status != "analysed":
        return []
    binds = len(analysis.binds)
    inputs = len(config.inputs)
    if binds == inputs:
        return []
    return [
        JdbcFinding(
            FACT,
            "bind-count-mismatch",
            f"The SQL has {binds} bind parameter(s) (`?`) but {inputs} input field(s) are "
            "configured for them.",
            "sql, inputField",
        )
    ]


def _signature_findings(service: FlowService, config: JdbcServiceConfig) -> list[JdbcFinding]:
    configured = {item.field for item in config.inputs if item.field} | {
        item.field for item in config.variables if item.field
    }
    extra = [
        field.name
        for field in input_fields(service)
        if field.name not in configured
        and field.name not in {CONNECTION_OVERRIDE_FIELD, CREDENTIALS_OVERRIDE_RECORD}
    ]
    if not extra or not (config.inputs or config.variables):
        return []
    names = ", ".join(f"`{name}`" for name in extra)
    return [
        JdbcFinding(
            INFERRED,
            "unbound-signature-inputs",
            f"Input field(s) {names} are in the signature but not bound to the SQL "
            "(neither a bind parameter nor a variable): the configured statement does not "
            "use them.",
            "input signature, inputField, sqlInputFields",
        )
    ]


def _statement_findings(config: JdbcServiceConfig) -> list[JdbcFinding]:
    analysis = config.sql_analysis
    assert analysis is not None
    found: list[JdbcFinding] = []
    if analysis.status != "analysed":
        notes = "; ".join(analysis.notes) or "not understood"
        found.append(
            JdbcFinding(UNKNOWN, "sql-partly-read", f"The SQL was read in part: {notes}.", "sql")
        )
    no_row_limit = config.max_rows in (None, "", "0")
    if not no_row_limit:
        found.append(
            JdbcFinding(
                FACT, "max-rows", f"At most {config.max_rows} row(s) are returned.", "maxRow"
            )
        )
    if analysis.pagination and analysis.order_by is None:
        found.append(
            JdbcFinding(
                RISK,
                "pagination-without-order",
                "Rows are paged (" + ", ".join(analysis.pagination) + ") without an ORDER BY: "
                "which rows a page holds is not deterministic.",
                "sql",
            )
        )
    run_time_text = any(
        "other SQL text" in item.contexts or "object name" in item.contexts
        for item in analysis.placeholders
    )
    if (
        analysis.statement == "SELECT"
        and analysis.status == "analysed"
        and not analysis.where
        and not analysis.pagination
        and no_row_limit
        and not run_time_text
    ):
        found.append(
            JdbcFinding(
                RISK,
                "unbounded-query",
                "The SELECT has no WHERE clause, no row limit in the SQL and no maximum row "
                "count: it returns every row of its tables.",
                "sql, maxRow",
            )
        )
    if run_time_text:
        found.append(
            JdbcFinding(
                UNKNOWN,
                "statement-known-at-run-time",
                "Part of the statement (a table name or a clause) is substituted at run time; "
                "what it reads or changes there is not known statically.",
                "sql",
            )
        )
    if analysis.for_update:
        found.append(
            JdbcFinding(
                FACT, "locks-rows", "The SELECT locks the rows it reads (FOR UPDATE).", "sql"
            )
        )
    return found


# --- callers ---------------------------------------------------------------------------


def adapter_uses(
    adapter: FlowService,
    callers: Iterable[FlowService],
    inputs: CallInputs,
    *,
    limit: int = MAX_CALLERS,
) -> tuple[list[AdapterUse], int]:
    """Each call of `adapter` by a FLOW caller (at most `limit` callers); callers left out."""
    name = adapter.identity.full_name
    flow_callers = sorted(
        {
            caller.identity.full_name: caller
            for caller in callers
            if caller.flow_tree is not None and caller.identity.full_name != name
        }.values(),
        key=lambda caller: (caller.identity.full_name.casefold(), caller.identity.full_name),
    )
    probes = probe_paths(adapter)
    uses: list[AdapterUse] = []
    for caller in flow_callers[:limit]:
        uses += caller_uses(caller, name, probes, inputs)
    return uses[:MAX_USES], max(len(flow_callers) - limit, 0)


def probe_paths(adapter: FlowService) -> list[tuple[str, str]]:
    """(signature path, role) of the adapter inputs whose caller values matter."""
    config = jdbc_config(adapter)
    paths: list[tuple[str, str]] = []
    if config is not None and config.supported:
        record = config.input_record
        for variable in config.variables:
            if variable.field:
                path = f"{record}/{variable.field}" if record else variable.field
                paths.append((path, "substitution"))
    if config is not None and has_input(adapter, CONNECTION_OVERRIDE_FIELD):
        paths.append((CONNECTION_OVERRIDE_FIELD, "connection override"))
    return paths


def caller_uses(
    caller: FlowService,
    adapter_name: str,
    probes: list[tuple[str, str]],
    inputs: CallInputs,
) -> list[AdapterUse]:
    """The calls of `adapter_name` in `caller`, with loops and what each input map passes."""
    if caller.flow_tree is None:
        return []
    loops = _loops_by_call(caller.flow_tree)
    calls = sorted(
        (
            call
            for call in caller.call_occurrences
            if call.target == adapter_name and call.call_type is CallType.INVOKE
        ),
        key=lambda call: call.order,
    )
    uses: list[AdapterUse] = []
    for number, call in enumerate(calls, start=1):
        given = inputs(caller, call.id)
        passes = []
        for path, role in probes:
            found = given.get(path.casefold())
            passes.append(
                FieldPass(
                    path=path,
                    role=role,
                    display=found[0] if found is not None else None,
                    how=found[1] if found is not None else "not set in the call's input map",
                )
            )
        uses.append(
            AdapterUse(
                caller=caller.identity.full_name,
                call_id=f"call {number}" if len(calls) > 1 else "its call",
                adapter=adapter_name,
                loops=loops.get(call.id, ()),
                passes=tuple(passes),
            )
        )
    return uses


def caller_lines(
    caller: FlowService, services: Mapping[str, FlowService], inputs: CallInputs
) -> tuple[str, ...]:
    """Plain-text facts on the decoded JDBC adapter services `caller` calls directly."""
    if caller.flow_tree is None:
        return ()
    targets = sorted(
        {call.target for call in caller.call_occurrences if call.call_type is CallType.INVOKE},
        key=lambda name: (name.casefold(), name),
    )
    lines: list[str] = []
    for target in targets:
        adapter = services.get(target)
        config = jdbc_config(adapter) if adapter is not None else None
        if adapter is None or config is None or not config.supported:
            continue
        for use in caller_uses(caller, target, probe_paths(adapter), inputs):
            parts = ["inside " + " > ".join(use.loops) if use.loops else "not inside a loop"]
            for item in use.passes:
                value = item.display if item.display is not None else "not set in its input map"
                parts.append(f"{item.path} ({item.role}): {value}")
            lines.append(f"`{target}` {use.call_id}: " + "; ".join(parts))
    if len(lines) > MAX_CALLER_LINES:
        extra = len(lines) - MAX_CALLER_LINES
        lines = [*lines[:MAX_CALLER_LINES], f"... and {extra} more call(s)"]
    return tuple(lines)


def _loops_by_call(root: FlowNode) -> dict[str, tuple[str, ...]]:
    found: dict[str, tuple[str, ...]] = {}

    def visit(node: FlowNode, around: tuple[str, ...]) -> None:
        if node.type is FlowNodeType.LOOP:
            around = (*around, f"LOOP over `{node.in_array}`" if node.in_array else "LOOP")
        elif node.type is FlowNodeType.REPEAT:
            around = (*around, "REPEAT")
        if node.call_occurrence_id is not None:
            found[node.call_occurrence_id] = around
        for child in node.children:
            visit(child, around)

    visit(root, ())
    return found


def use_findings(uses: Iterable[AdapterUse]) -> list[JdbcFinding]:
    """Findings about how callers use one adapter service."""
    found: list[JdbcFinding] = []
    for use in uses:
        where = f"`{use.caller}` ({use.call_id})"
        loops = [loop for loop in use.loops if loop.startswith("LOOP")]
        if loops:
            found.append(
                JdbcFinding(
                    RISK,
                    "query-in-loop",
                    f"{where} runs the statement inside a {loops[-1]}: once per item. If the "
                    "items come from an earlier query this is an N+1 query pattern.",
                    "FLOW structure",
                )
            )
        for item in use.passes:
            if item.role == "connection override" and item.display is not None:
                found.append(
                    JdbcFinding(
                        FACT,
                        "connection-overridden",
                        f"{where} sets `{item.path}` {_value_phrase(item)} in its input map: "
                        "the statement may run on another connection than the configured one.",
                        "caller input map",
                    )
                )
            if item.role == "substitution":
                found.append(_substitution_source(where, item))
    return found


def _value_phrase(item: FieldPass) -> str:
    if item.how == "literal":
        return f"to {item.display}"
    return item.display or ""


def _substitution_source(where: str, item: FieldPass) -> JdbcFinding:
    if item.how == "literal":
        return JdbcFinding(
            FACT,
            "substitution-literal",
            f"{where} sets `{item.path}` to {item.display} (a fixed text) in its input map.",
            "caller input map",
        )
    if item.how == "mapped from pipeline":
        return JdbcFinding(
            INFERRED,
            "substitution-mapped",
            f"{where} maps `{item.path}` {item.display} in its input map: that value becomes "
            "SQL text.",
            "caller input map",
        )
    return JdbcFinding(
        UNKNOWN,
        "substitution-from-pipeline",
        f"{where} does not set `{item.path}` in its input map: the value comes from the "
        "pipeline as it is when the call starts.",
        "caller input map",
    )


def shared_writes(services: Mapping[str, FlowService]) -> dict[str, list[str]]:
    """Table -> the adapter services whose SQL writes it, for tables written by two or more."""
    writers: dict[str, set[str]] = {}
    for name, service in services.items():
        config = jdbc_config(service)
        if config is None or config.sql_analysis is None:
            continue
        for item in config.sql_analysis.objects:
            if item.access in {"write", "read-write"}:
                table = f"{item.schema_name}.{item.name}" if item.schema_name else item.name
                writers.setdefault(table.upper(), set()).add(name)
    return {
        table: sorted(names, key=str.casefold)
        for table, names in sorted(writers.items())
        if len(names) > 1
    }
