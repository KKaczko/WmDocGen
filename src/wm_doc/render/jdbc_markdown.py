"""Markdown for a decoded JDBC adapter service: SQL, parameters, objects and findings.

Used by the service page under `## Adapter Configuration` and by the facts block of
description files. The SQL template is shown as the free-text policy allows (the secret
guard first); everything else is identifiers and structure from `AdapterDetails.jdbc`,
`jdbc_facts` findings and, for direct FLOW callers, what each call's input map passes into
text substitutions and `$connectionName`.
"""

from __future__ import annotations

from collections.abc import Iterable

from wm_doc.adapters import operation_phrase
from wm_doc.effects import call_inputs
from wm_doc.ir import FlowService, JdbcServiceConfig, TextDisclosure
from wm_doc.jdbc_facts import (
    KIND_LABELS,
    AdapterUse,
    JdbcFinding,
    adapter_findings,
    adapter_uses,
    use_findings,
)


def render_jdbc_section(service: FlowService, callers: Iterable[FlowService] = ()) -> str:
    """The JDBC part of an adapter service page; "" when nothing was decoded."""
    details = service.adapter
    config = details.jdbc if details is not None else None
    if details is None or config is None:
        return ""
    if not config.supported:
        return "\n".join(
            [
                "",
                f"The `{config.template_kind}` template is decoded but not interpreted (only "
                "`DynamicSQL` and `CustomSQL` were checked on real samples). Its properties: "
                + (", ".join(f"`{name}`" for name in config.uninterpreted) or "none")
                + ".",
            ]
        )
    lines = ["", "### SQL template", ""]
    lines += _sql_lines(config)
    lines += _statement_lines(service)
    lines += _parameter_lines(config)
    lines += _output_lines(config)
    lines += _settings_lines(config)
    uses, hidden = adapter_uses(service, callers, call_inputs)
    lines += ["", "### Findings", ""]
    lines += _finding_lines(adapter_findings(service) + use_findings(uses))
    lines += _caller_lines(uses, hidden)
    if config.uninterpreted:
        lines += [
            "",
            "Properties not interpreted: "
            + ", ".join(f"`{name}`" for name in config.uninterpreted)
            + ".",
        ]
    if config.issues:
        lines += ["", "Configuration issues: " + "; ".join(config.issues) + "."]
    return "\n".join(lines)


def _fence(text: str) -> str:
    longest = run = 0
    for char in text:
        run = run + 1 if char == "`" else 0
        longest = max(longest, run)
    return "`" * max(3, longest + 1)


def _sql_lines(config: JdbcServiceConfig) -> list[str]:
    sql = config.sql
    if sql is None:
        return ["No SQL template is configured."]
    if sql.disclosure is TextDisclosure.INCLUDED and sql.value is not None:
        fence = _fence(sql.value)
        lines = ["The SQL exactly as configured:", "", f"{fence}sql", sql.value, fence]
        if config.variables:
            lines += [
                "",
                "`${name}` parts are replaced by the text of an input before the statement "
                "runs; `?` are JDBC bind parameters.",
            ]
        return lines
    reason = (
        "withheld because it looks like it holds a secret"
        if sql.disclosure is TextDisclosure.BLOCKED_SECRET
        else "withheld by the free-text policy"
    )
    return [f"The SQL text ({sql.length} characters) is {reason}."]


def _statement_lines(service: FlowService) -> list[str]:
    details = service.adapter
    assert details is not None and details.jdbc is not None
    analysis = details.jdbc.sql_analysis
    if analysis is None:
        return []
    lines = [
        "",
        "### Database operations",
        "",
        f"Statement: `{analysis.statement}` ({operation_phrase(details)}); "
        f"{_STATUS[analysis.status]} by wm-doc, never executed.",
        "",
    ]
    if analysis.objects:
        lines += ["| Table or view | Schema | Access | Clauses |", "| --- | --- | --- | --- |"]
        lines += [
            f"| `{item.name}` | {f'`{item.schema_name}`' if item.schema_name else '-'} | "
            f"{item.access} | {', '.join(item.clauses)} |"
            for item in analysis.objects
        ]
    else:
        lines.append("No table or view is named in the SQL.")
    if analysis.procedure:
        lines += ["", f"Calls procedure `{analysis.procedure}`."]
    shape = [
        f"WHERE: {'yes' if analysis.where else 'no'}",
        f"ORDER BY: {analysis.order_by or 'none'}",
        "pagination: " + (", ".join(analysis.pagination) or "none"),
    ]
    if analysis.joins:
        shape.append(f"joins: {analysis.joins}")
    if analysis.subqueries:
        shape.append(f"subqueries: {analysis.subqueries}")
    if analysis.ctes:
        shape.append("CTEs: " + ", ".join(f"`{name}`" for name in analysis.ctes))
    if analysis.group_by:
        shape.append("GROUP BY: yes")
    if analysis.set_operations:
        shape.append("set operations: " + ", ".join(analysis.set_operations))
    lines += ["", "; ".join(shape) + "."]
    if analysis.notes:
        lines += ["", "Notes: " + "; ".join(analysis.notes) + "."]
    return lines


_STATUS = {
    "analysed": "read completely",
    "partial": "read in part (see the notes)",
    "not_analysed": "not read",
}


def _parameter_lines(config: JdbcServiceConfig) -> list[str]:
    lines: list[str] = []
    analysis = config.sql_analysis
    if config.inputs:
        lines += [
            "",
            "### Bind parameters",
            "",
            "Each `?` of the SQL, in order, takes the input at the same position.",
            "",
            "| # | Input field | Java type | JDBC type | In the SQL |",
            "| ---: | --- | --- | --- | --- |",
        ]
        for item in config.inputs:
            bind = (
                analysis.binds[item.position - 1]
                if analysis is not None and item.position <= len(analysis.binds)
                else None
            )
            if bind is None:
                where = "no matching `?`" if analysis is not None else "-"
            elif bind.column:
                where = f"{bind.operator or ''} `{bind.column}`".strip()
            else:
                where = bind.role if bind.role != "value" else "-"
            lines.append(
                f"| {item.position} | `{item.field or '-'}` | `{item.field_type or '-'}` | "
                f"`{item.jdbc_type or '-'}` | {where} |"
            )
    if config.variables:
        placeholders = (
            {item.name: item for item in analysis.placeholders} if analysis is not None else {}
        )
        lines += [
            "",
            "### Text substitutions",
            "",
            "| Variable | Input field | Java type | Where it stands |",
            "| --- | --- | --- | --- |",
        ]
        for variable in config.variables:
            found = placeholders.get(variable.name)
            where = (
                ", ".join(found.contexts) + (f" for `{found.column}`" if found.column else "")
                if found is not None
                else "not in the SQL"
            )
            lines.append(
                f"| `${{{variable.name}}}` | `{variable.field or '-'}` | "
                f"`{variable.field_type or '-'}` | {where} |"
            )
    return lines


def _output_lines(config: JdbcServiceConfig) -> list[str]:
    if not config.outputs and not config.sql_output_field:
        return []
    lines = [
        "",
        "### Results",
        "",
        "| # | Column field | JDBC type | Returned as | Type |",
        "| ---: | --- | --- | --- | --- |",
    ]
    lines += [
        f"| {item.position} | `{item.field or '-'}` | `{item.jdbc_type or '-'}` | "
        f"`{item.result_field or '-'}` | `{item.result_type or '-'}` |"
        for item in config.outputs
    ]
    if config.sql_output_field:
        lines += [
            "",
            f"`{config.sql_output_field}` returns the statement as run (a technical output, "
            "not a business result).",
        ]
    return lines


def _settings_lines(config: JdbcServiceConfig) -> list[str]:
    rows = [
        ("Maximum rows", config.max_rows, "0 means no limit is set"),
        ("Query timeout", config.query_timeout, "-1 means the default"),
        ("Row count field", config.result_row_field, "empty means none"),
        ("Metadata version", _text(config.metadata_version), ""),
        ("Adapter service node version", _text(config.node_version), ""),
    ]
    lines = ["", "### Settings", "", "| Setting | Value | Note |", "| --- | --- | --- |"]
    for label, value, note in rows:
        shown = "not set" if value is None else ("(empty)" if value == "" else f"`{value}`")
        lines.append(f"| {label} | {shown} | {note} |")
    return lines


def _text(value: int | None) -> str | None:
    return None if value is None else str(value)


def _finding_lines(findings: list[JdbcFinding]) -> list[str]:
    if not findings:
        return ["None."]
    return [f"- **{KIND_LABELS[item.kind]}**: {item.text} ({item.basis})" for item in findings]


def _caller_lines(uses: list[AdapterUse], hidden: int) -> list[str]:
    if not uses:
        return []
    lines = [
        "",
        "### How callers use it",
        "",
        "From each direct FLOW caller's input map for the call (a field it does not set comes "
        "from the pipeline as it is when the call starts).",
        "",
    ]
    for use in uses:
        loops = "inside " + " > ".join(use.loops) if use.loops else "not inside a loop"
        passes = "; ".join(
            f"`{item.path}` ({item.role}): {item.display or 'not set in its input map'}"
            for item in use.passes
        )
        lines.append(
            f"- `{use.caller}` ({use.call_id}): {loops}" + (f"; {passes}" if passes else "")
        )
    if hidden:
        lines.append(f"- ... and {hidden} more caller(s), not read")
    return lines
