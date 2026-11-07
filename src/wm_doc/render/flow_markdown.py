"""The "Decisions" section of a service page, from the derived control model (`flow_logic`).

Conditions are shown as written in the FLOW and never evaluated. Every row says how certain it
is; rows resting on an Integration Server rule not yet confirmed on 10.15 name the assumption.
Rule citations come from the registry (`rule_label`, `assumption_label`) and are never written
by hand, so a status change in `flow_semantics` reaches every page. Label text only ever appears
flattened inside code spans, so it cannot form Markdown structure.
"""

from __future__ import annotations

from wm_doc.call_targets import TargetStatus
from wm_doc.flow_lineage import (
    MAX_DECISIONS,
    MAX_PATHS_PER_DECISION,
    MAX_TRACKED_PATHS,
    FlowLineage,
    MapRole,
    Origin,
    OriginKind,
    VariableOrigins,
)
from wm_doc.flow_logic import (
    CallContext,
    Certainty,
    ConditionKind,
    Decision,
    DecisionCase,
    DecisionMode,
    ExitEffect,
    ExitScope,
    FlowLogic,
    Guard,
    GuardKind,
    GuardTerm,
    Reach,
    code_span,
    sort_rules,
    weakest,
)
from wm_doc.flow_scenarios import (
    MAX_CHAIN,
    MAX_SCENARIOS,
    FlowScenarios,
    Outcome,
    OutcomeKind,
    RuledOut,
    Scenario,
    ScenarioTable,
)
from wm_doc.flow_semantics import RULES, assumption_label, rule_label
from wm_doc.ir import CallType, MappingOperationType

MAX_DECISIONS_SHOWN = 40
MAX_CALL_ROWS = 100
MAX_LIST_ROWS = 40
MAX_CASE_CALLS = 10
MAX_EXITING_TERMS = 3  # NOT_CASES / MAY_BE_SKIPPED terms shown before "and N more"
MAX_IDS = 5

INTRO = (
    "When each step runs, read from the FLOW structure; conditions are shown as written and "
    "never evaluated. D1, C1 and E1 number the decisions (BRANCH steps), calls and EXIT steps "
    "in the order they appear. A normal run is one in which no step fails on its own; steps "
    'that run only after a failure say so. "derived" follows from the FLOW and the Integration '
    'Server rules in [LIMITATIONS.md](../LIMITATIONS.md); "assumption S#" marks a rule not yet '
    "confirmed on IS 10.15."
)


def note_text(note: str) -> str:
    """A decision note in words, citing its rules by their current status."""
    if note == "SWITCH_IGNORED":
        return (
            "It also names a switch, which is not valid together with label expressions "
            f"({rule_label(['S8'])}); the switch is not used here."
        )
    if note == "NO_SWITCH":
        return "It has no switch and its labels are not expressions; IS behaviour is unknown."
    if note == "DEFAULT_NOT_LAST":
        return (
            "`$default` is not the last case; it runs only when no other case matches "
            f"({rule_label(['S6'])})."
        )
    if note == "DUPLICATE_LABEL":
        return (
            "A case repeats an earlier label, which Designer does not allow; the first one wins, "
            f"so the repeat never runs ({rule_label(['S2', 'S37'])})."
        )
    if note == "LABELS_IGNORED":
        return (
            "Label expressions ignore a blank or `$null` label, so such a case never runs "
            f"({rule_label(['S8'])})."
        )
    if note == "LABELS_WITHHELD":
        return "Some case labels are withheld by the free-text policy."
    if note == "EXPRESSION_NOT_SPLIT":
        return "Some label expressions could not be split into field references."
    return note

MAX_VARIABLES_SHOWN = 5
MAX_ORIGINS_SHOWN = 8
MAX_SOURCE_ORIGINS = 4
MAX_ORIGIN_LINES = 30  # chain lines under one field
MAX_SUMMARY_ORIGINS = 4
MAX_COPY_DEPTH_SHOWN = 5  # nesting of "where the copied field comes from" lines
MAX_FACT_CASES = 40  # cases per decision in a description file's facts block

ORIGINS_INTRO = (
    'Under each decision, "Where ... comes from" lists what may have set each field it tests '
    "on the paths that reach it: mapping lines, values a called service may leave, the "
    'service\'s inputs or the caller\'s pipeline. "Comes from" means exactly one observed '
    'definition reaches the decision and no call runs in between; otherwise it says "may come '
    'from". Fields are matched by their exact path, never by a similar name.'
)

UNFOLLOWED_TEXT = {
    "no_switch": "It has no switch, so there is no field to follow.",
    "labels_withheld": (
        "Some label expressions are withheld, so not every field they test is known."
    ),
    "expression_not_split": (
        "Some label expressions could not be split into fields; those fields are not followed."
    ),
    "too_many_fields": (
        f"Only the first {MAX_PATHS_PER_DECISION} fields its label expressions test are followed."
    ),
    "decision_limit": (
        f"Its fields are not followed: only those of the first {MAX_DECISIONS} decisions are."
    ),
}

_TARGET_TEXT = {
    TargetStatus.RESOLVED: "an analysed service",
    TargetStatus.PLATFORM: "a built-in service",
    TargetStatus.OUTSIDE: "outside the analysed packages",
}

_NOTE_SUFFIX = {
    "list_element": "the line writes one list element",
    "conditional": "the line has attributes that are not interpreted, possibly a condition",
    "several_writes": (
        "another line of the same map also writes it, and which one is applied last is not "
        "documented"
    ),
    "source_may_be_absent": "when the source is absent the field keeps its earlier value",
    "not_followed": "the source is not followed further",
    "source_unknown": "the source path is not known",
}


def render_decisions_section(
    logic: FlowLogic | None,
    lineage: FlowLineage | None = None,
    scenarios: FlowScenarios | None = None,
) -> str:
    """The section body (without its heading), or "" when there is nothing conditional."""
    if logic is None or not logic.significant:
        return ""
    parts = [INTRO]
    if lineage is not None and lineage.variables:
        parts.append(ORIGINS_INTRO)
    parts += [
        _decision_block(logic, item, lineage) for item in logic.decisions[:MAX_DECISIONS_SHOWN]
    ]
    parts += _more(len(logic.decisions), MAX_DECISIONS_SHOWN, "decision")
    if lineage is not None and lineage.limits:
        parts.append("Origin limits: " + "; ".join(lineage.limits) + ".")
    if scenarios is not None and scenarios.tables:
        parts.append(render_scenarios(logic, scenarios))
    if logic.calls:
        parts.append(_calls_block(logic))
    if logic.exits:
        parts.append(_exits_block(logic))
    if logic.unreachable:
        parts.append(_unreachable_block(logic))
    if logic.limits:
        parts.append("Limits: " + "; ".join(logic.limits) + ".")
    return "\n\n".join(parts)


def rules_markdown() -> str:
    """The rule table for LIMITATIONS.md."""
    lines = [
        "## Conditional FLOW rules",
        "",
        "The Decisions section of a service page rests on these Integration Server rules. Rules "
        "marked assumed are not yet confirmed on IS 10.15.",
        "",
        "| Rule | Topic | Statement | Status |",
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| {rule.id} | {rule.topic} | {_cell(rule.statement)} | {rule.status.value} |"
        for rule in RULES
    ]
    return "\n".join(lines) + "\n"


# --- decisions -----------------------------------------------------------------------------


def decision_title(decision: Decision) -> str:
    """`D1: BRANCH on `/x` (line 5)`, without Markdown structure."""
    line = f" (line {decision.source.line})" if decision.source.line else ""
    if decision.mode is DecisionMode.EXPRESSIONS:
        return f"{decision.id}: BRANCH with label expressions{line}"
    if decision.switch is not None:
        return f"{decision.id}: BRANCH on {code_span(decision.switch.text())}{line}"
    return f"{decision.id}: BRANCH without a switch{line}"


def _decision_block(logic: FlowLogic, decision: Decision, lineage: FlowLineage | None) -> str:
    lines = [f"### {decision_title(decision)}", ""]
    if decision.guard.terms:
        lines += [f"Evaluated only when: {guard_text(logic, decision.guard)}.", ""]
    if decision.loop_id is not None:
        lines += ["It is inside a loop, so each iteration may take a different case.", ""]
    for note in decision.notes:
        lines += [note_text(note), ""]
    lines += [
        "| Case | Condition | Calls, in order | Ends with | Notes |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in decision.cases:
        calls = [_call_ref(logic, call_id) for call_id in case.call_ids[:MAX_CASE_CALLS]]
        hidden = len(case.call_ids) - min(len(case.call_ids), MAX_CASE_CALLS)
        if hidden:
            calls.append(f"and {hidden} more")
        ends = [_exit_ref(logic, exit_id) for exit_id in case.ends_with[:MAX_IDS]]
        if len(case.ends_with) > MAX_IDS:
            ends.append(f"and {len(case.ends_with) - MAX_IDS} more")
        notes = []
        if case.unreachable_rule:
            notes.append(f"never runs ({rule_label([case.unreachable_rule])})")
        label = assumption_label(case.rules)
        if label:
            notes.append(label)
        lines.append(
            f"| {case.id} | {_cell(condition_text(decision, case))} | "
            f"{_cell(', '.join(calls)) or '-'} | {_cell(', '.join(ends)) or '-'} | "
            f"{_cell('; '.join(notes)) or '-'} |"
        )
    if decision.falls_through:
        lines.append(f"| - | no case matches | - | - | {_cell(no_match_text(decision))} |")
    if lineage is not None:
        lines += _origins_block(logic, lineage, decision)
    return "\n".join(lines)


def no_match_text(decision: Decision) -> str:
    """What happens when no case matches; never only "the next step follows" when it may fail."""
    falls = f"nothing runs and the next step follows ({rule_label(['S7'])})"
    if not decision.missing_fails:
        return falls
    field = code_span(decision.switch.text()) if decision.switch else "the switch value"
    unless = (
        ", unless a withheld label is `$null`" if "LABELS_WITHHELD" in decision.notes else ""
    )
    return (
        f"nothing runs and the next step follows when {field} has a value no case matches "
        f"({rule_label(['S7'])}); when {field} is missing the BRANCH fails instead{unless} "
        f"({rule_label(['S31'])})"
    )


def condition_text(decision: Decision, case: DecisionCase) -> str:
    """The case condition in words; values only as the free-text policy allows."""
    field = code_span(decision.switch.text()) if decision.switch else "the switch value"
    condition = case.condition
    kind = condition.kind
    if kind is ConditionKind.VALUE:
        text = f"{field} is {code_span(condition.text or '')}"
    elif kind is ConditionKind.NULL:
        text = f"{field} is missing or null"
    elif kind is ConditionKind.EMPTY:
        text = f"{field} is an empty string"
    elif kind is ConditionKind.PATTERN:
        text = f"{field} matches the pattern {code_span(condition.text or '')}"
    elif kind is ConditionKind.EXPRESSION:
        text = code_span(condition.text or "")
    elif kind is ConditionKind.DEFAULT:
        return "no other case matches"
    elif kind is ConditionKind.UNLABELLED:
        text = "(no condition written)"
    else:
        text = "(label withheld)"
    if case.excludes:
        text += ", and no earlier case matched"
    return text


def case_short(case: DecisionCase) -> str:
    """A compact case name for guard text: `ACTIVE`, missing or null, otherwise, ..."""
    condition = case.condition
    kind = condition.kind
    if kind is ConditionKind.VALUE:
        return code_span(condition.text or "")
    if kind is ConditionKind.NULL:
        return "missing or null"
    if kind is ConditionKind.EMPTY:
        return "empty"
    if kind is ConditionKind.PATTERN:
        return f"matches {code_span(condition.text or '')}"
    if kind is ConditionKind.EXPRESSION:
        text = code_span(condition.text or "")
        return f"{text} (and no earlier case)" if case.excludes else text
    if kind is ConditionKind.DEFAULT:
        return "otherwise"
    if kind is ConditionKind.UNLABELLED:
        return f"case {case.index} (no condition)"
    return f"case {case.index} (label withheld)"


# --- origins -------------------------------------------------------------------------------


def _origins_block(logic: FlowLogic, lineage: FlowLineage, decision: Decision) -> list[str]:
    lines: list[str] = []
    for reason in lineage.unfollowed.get(decision.id, ()):
        lines += ["", UNFOLLOWED_TEXT.get(reason, reason)]
    variables = lineage.for_decision(decision.id)
    for variable in variables[:MAX_VARIABLES_SHOWN]:
        lines += ["", f"Where {code_span(variable.path.text())} comes from:", ""]
        lines += variable_lines(logic, lineage, variable)
    hidden = len(variables) - min(len(variables), MAX_VARIABLES_SHOWN)
    if hidden:
        lines += ["", f"... and {hidden} more field(s) not shown."]
    return lines


def variable_lines(logic: FlowLogic, lineage: FlowLineage, variable: VariableOrigins) -> list[str]:
    """Markdown list lines saying where one decision field may come from."""
    blocked = _not_followed(variable)
    if blocked is not None:
        return [f"- {blocked}"]
    lines: list[str] = []
    if variable.loop_path is not None:
        lines.append(
            f"- Inside the LOOP over {code_span(variable.loop_path.text())}, that path names the "
            "current element (S22)."
        )
    if "list_element" in variable.notes:
        lines.append(
            "- The decision tests one list element; the origins below are those of the whole "
            "field, so none of them is certain."
        )
    origins = [lineage.origin(origin_id) for origin_id in variable.origins]
    budget = [MAX_ORIGIN_LINES]
    expanded: set[str] = set()
    if variable.unique:
        lines.append(f"- Comes from: {origin_text(logic, origins[0])}.")
        lines += _source_lines(logic, lineage, origins[0], 1, expanded, budget)
    elif len(origins) == 1 and origins[0].kind is OriginKind.CALLER:
        lines.append(
            "- Not set by this service before this decision; present only if the caller "
            f"supplies it ({origins[0].certainty.value})."
        )
    else:
        lines.append("- May come from any of:")
        for origin in origins[:MAX_ORIGINS_SHOWN]:
            lines.append(f"  - {origin_text(logic, origin)}")
            lines += _source_lines(logic, lineage, origin, 2, expanded, budget)
        hidden = len(origins) - min(len(origins), MAX_ORIGINS_SHOWN)
        if hidden:
            lines.append(f"  - and {hidden} more")
    if variable.calls_in_between:
        lines.append(
            "- Calls that run before the decision may also change it, because a called service "
            "shares the pipeline (S16): "
            f"{_calls_text(logic, variable.calls_in_between, variable.more_calls_in_between)}."
        )
    if variable.depends_on_calls:
        lines.append(
            "- It may carry what these calls return: "
            f"{_calls_text(logic, variable.depends_on_calls, False)}."
        )
    return lines


def _not_followed(variable: VariableOrigins) -> str | None:
    if "scope" in variable.notes:
        return (
            "Not followed: the decision is inside a step that works on one document (a scope), "
            f"so its fields are relative to that document ({rule_label(['S24'])})."
        )
    if "too_deep" in variable.notes:
        return "Not followed: the decision is nested too deeply."
    if "not_followed" in variable.notes:
        return f"Not followed: at most {MAX_TRACKED_PATHS} fields are followed per service."
    if not variable.reached:
        return "Not reached on any path the analysis knows, so nothing reaches it."
    return None


def _source_lines(
    logic: FlowLogic,
    lineage: FlowLineage,
    origin: Origin,
    level: int,
    expanded: set[str],
    budget: list[int],
) -> list[str]:
    """Where the field a copy reads may come from, indented under the copy."""
    if origin.kind is not OriginKind.COPY or origin.source_path is None:
        return []
    if not origin.source_origins:
        return []
    if origin.id in expanded or level > MAX_COPY_DEPTH_SHOWN:
        return []
    expanded.add(origin.id)
    pad = "  " * level
    path = code_span(origin.source_path.text())
    lines: list[str] = []
    sources = [lineage.origin(origin_id) for origin_id in origin.source_origins]
    shown = 0
    for source in sources[:MAX_SOURCE_ORIGINS]:
        if budget[0] <= 0:
            break
        budget[0] -= 1
        shown += 1
        repeat = " (as above)" if source.id in expanded else ""
        lines.append(f"{pad}- {path}: {origin_text(logic, source)}{repeat}")
        lines += _source_lines(logic, lineage, source, level + 1, expanded, budget)
    if len(sources) > shown:
        lines.append(f"{pad}- {path}: and {len(sources) - shown} more")
    return lines


def origin_text(logic: FlowLogic, origin: Origin, *, brief: bool = False) -> str:
    """One origin in words: what, where, when it runs and how certain it is."""
    text = _origin_what(logic, origin, brief=brief)
    if not brief:
        extras = [_NOTE_SUFFIX[note] for note in origin.notes if note in _NOTE_SUFFIX]
        if extras:
            text += f" ({'; '.join(extras)})"
    if origin.guard.terms:
        text += f", only when {guard_text(logic, origin.guard)}"
    if brief:
        return text
    certainty = weakest((origin.certainty, origin.guard.certainty))
    label = assumption_label(sort_rules((*origin.rules, *origin.guard.rules)))
    return f"{text} ({certainty.value}; {label})" if label else f"{text} ({certainty.value})"


def _origin_what(logic: FlowLogic, origin: Origin, *, brief: bool) -> str:
    kind = origin.kind
    where = _where(logic, origin)
    call = _call_name(logic, origin.call_id)
    if kind is OriginKind.SET:
        if origin.written_path is not None:
            what = (
                "set as part of a document value written to "
                f"{code_span(origin.written_path.text())}"
            )
        elif origin.value is None:
            what = "set to a value the literal policy does not show"
        elif origin.template:
            what = f"set from the template {code_span(origin.value)}"
        else:
            what = f"set to {code_span(origin.value)}"
        text = f"{what} in {where}"
        if "overwrite_off" in origin.notes:
            text += ", only if it has no value yet (overwrite off)"
        return text
    if kind is OriginKind.COPY:
        source = (
            code_span(origin.source_path.text())
            if origin.source_path is not None
            else "a field that is not known"
        )
        text = f"copied from {source} in {where}"
        if origin.written_path is not None:
            text += f", which copies a whole {code_span(origin.written_path.text())}"
        return text
    if kind is OriginKind.TRANSFORMER:
        output = (
            code_span(origin.source_path.text()) if origin.source_path is not None else "an output"
        )
        text = f"copied from output {output} of transformer {call}{_line(origin)}"
        if origin.inputs and not brief:
            given = ", ".join(code_span(item.text()) for item in origin.inputs)
            text += f", which is given {given}"
        return text
    if kind is OriginKind.CALL_RESPONSE:
        reasons = []
        if "declared_output" in origin.notes:
            declared = (
                f" {code_span(origin.declared_path.text())}"
                if origin.declared_path is not None
                else ""
            )
            reasons.append(f"it declares the output{declared}")
        if "output_map_reads" in origin.notes:
            reasons.append("its output map reads this field")
        status = _call_status(logic, origin.call_id)
        text = f"may be left by {call}{_line(origin)}: {' and '.join(reasons)}"
        return f"{text} ({status})" if status and not brief else text
    if kind is OriginKind.DROPPED:
        return f"dropped in {where}, so it is absent"
    if kind is OriginKind.CLEARED:
        return (
            f"removed by {call}{_line(origin)}, unless its `preserve` list names it (that list "
            "may come from the pipeline)"
        )
    if kind is OriginKind.RESTORED:
        return f"may be put back to a saved value by {call}{_line(origin)}"
    if kind is OriginKind.PARTIAL:
        verb = {
            MappingOperationType.COPY: "copies into",
            MappingOperationType.SET: "sets",
            MappingOperationType.DELETE: "drops",
        }.get(origin.operation or MappingOperationType.SET, "writes")
        written = code_span(origin.written_path.text()) if origin.written_path else "a field in it"
        return f"partly changed: a line {verb} {written} in {where}"
    if kind is OriginKind.LINKED:
        written = code_span(origin.written_path.text()) if origin.written_path else "a field"
        return (
            f"may be changed in place when {where} writes {written}, the same field of a "
            f"document linked to this one ({rule_label(['S38'])})"
        )
    if kind is OriginKind.COLLECTED:
        return f"collected by {_step(logic, origin.node_id)} (OUT-ARRAY)"
    if kind is OriginKind.SERVICE_INPUT:
        field = origin.declared_path
        if field is None or field == origin.path:
            return "a declared input of this service, not changed on this path"
        return f"part of the declared input {code_span(field.text())}, not changed on this path"
    if kind is OriginKind.CALLER:
        if brief:
            return "the caller's pipeline (this service does not set it on this path)"
        return "not set by this service on this path; present only if the caller supplies it"
    step = _step(logic, origin.node_id)
    if "scope" in origin.notes:
        return f"may be changed inside {step}, which works on one document (a scope; not followed)"
    if "deep_loop" in origin.notes:
        return f"may be changed by repeated runs of {step} (not followed)"
    return f"may be changed inside {step} (nested too deeply; not followed)"


def _where(logic: FlowLogic, origin: Origin) -> str:
    call = _call_name(logic, origin.call_id)
    role = origin.map_role
    if role is MapRole.CALL_INPUT:
        return f"the input map of {call}{_line(origin)}"
    if role is MapRole.CALL_OUTPUT:
        return f"the output map of {call}{_line(origin)}"
    if role is MapRole.TRANSFORMER_OUTPUT:
        return f"the output map of transformer {call}{_line(origin)}"
    return _step(logic, origin.node_id)


def _step(logic: FlowLogic, node_id: str | None) -> str:
    return logic.step_text.get(node_id or "", "a step") if node_id else "a step"


def _line(origin: Origin) -> str:
    return f" (line {origin.line})" if origin.line else ""


def _call_name(logic: FlowLogic, call_id: str | None) -> str:
    if call_id is None:
        return "a call"
    return f"{call_id} {code_span(logic.call(call_id).target)}"


def _call_status(logic: FlowLogic, call_id: str | None) -> str | None:
    if call_id is None:
        return None
    status = logic.call(call_id).target_status
    return _TARGET_TEXT.get(status, "a target that is not resolved")


def _calls_text(logic: FlowLogic, call_ids: tuple[str, ...], more: bool) -> str:
    text = ", ".join(_call_name(logic, call_id) for call_id in call_ids)
    return f"{text} and more" if more else text


def origin_summary(logic: FlowLogic, lineage: FlowLineage, variable: VariableOrigins) -> str:
    """One line for the facts block of a description file."""
    blocked = _not_followed(variable)
    if blocked is not None:
        return blocked[0].lower() + blocked[1:].rstrip(".")
    origins = [lineage.origin(origin_id) for origin_id in variable.origins]
    if variable.unique:
        text = f"comes from: {origin_text(logic, origins[0], brief=True)}"
    elif len(origins) == 1 and origins[0].kind is OriginKind.CALLER:
        text = "not set by this service before; present only if the caller supplies it"
    else:
        shown = "; ".join(
            origin_text(logic, origin, brief=True) for origin in origins[:MAX_SUMMARY_ORIGINS]
        )
        hidden = len(origins) - min(len(origins), MAX_SUMMARY_ORIGINS)
        text = f"may come from: {shown}" + (f"; and {hidden} more" if hidden else "")
    if variable.calls_in_between:
        calls = ", ".join(variable.calls_in_between)
        more = " and more" if variable.more_calls_in_between else ""
        text += f"; calls before it may change it: {calls}{more}"
    return text


def render_decision_facts(logic: FlowLogic | None, lineage: FlowLineage | None) -> str:
    """The "### Decisions" part of a description file's facts block, or ""."""
    if logic is None or not logic.significant or not logic.decisions:
        return ""
    lines = [
        "### Decisions",
        "",
        "Read from the FLOW; conditions as written and never evaluated. The service page gives "
        "the reasons and the assumptions.",
        "",
    ]
    for decision in logic.decisions[:MAX_DECISIONS_SHOWN]:
        head = f"- {decision_title(decision)}"
        if decision.guard.terms:
            head += f", evaluated only when {guard_text(logic, decision.guard)}"
        lines.append(head)
        for case in decision.cases[:MAX_FACT_CASES]:
            calls = [_call_ref(logic, call_id) for call_id in case.call_ids[:MAX_CASE_CALLS]]
            hidden = len(case.call_ids) - min(len(case.call_ids), MAX_CASE_CALLS)
            if hidden:
                calls.append(f"and {hidden} more")
            never = " (never runs)" if case.unreachable_rule else ""
            lines.append(
                f"  - {case.id} {_flat(condition_text(decision, case))}{never}: "
                f"{', '.join(calls) or 'no calls'}"
            )
        if len(decision.cases) > MAX_FACT_CASES:
            lines.append(f"  - ... and {len(decision.cases) - MAX_FACT_CASES} more case(s)")
        if decision.falls_through:
            text = "  - no case matches: nothing runs"
            if decision.missing_fails:
                field = code_span(decision.switch.text()) if decision.switch else "the switch"
                text += f"; if {field} is missing, the BRANCH fails"
            lines.append(text)
        if lineage is not None:
            for variable in lineage.for_decision(decision.id)[:MAX_VARIABLES_SHOWN]:
                lines.append(
                    f"  - {code_span(variable.path.text())}: "
                    f"{origin_summary(logic, lineage, variable)}"
                )
    if len(logic.decisions) > MAX_DECISIONS_SHOWN:
        lines.append(f"- ... and {len(logic.decisions) - MAX_DECISIONS_SHOWN} more decision(s)")
    return "\n".join(lines)


def _flat(text: str) -> str:
    return " ".join(text.split())


# --- guards --------------------------------------------------------------------------------


def guard_text(logic: FlowLogic, guard: Guard) -> str:
    if not guard.terms:
        return "every normal run"
    shown: list[str] = []
    exiting_hidden = 0
    exiting_seen = 0
    for term in guard.terms:
        if term.kind in (GuardKind.NOT_CASES, GuardKind.MAY_BE_SKIPPED):
            exiting_seen += 1
            if exiting_seen > MAX_EXITING_TERMS:
                exiting_hidden += 1
                continue
        shown.append(term_text(logic, term))
    if exiting_hidden:
        shown.append(f"and {exiting_hidden} more earlier step(s) did not leave first")
    return "; ".join(shown)


def term_text(logic: FlowLogic, term: GuardTerm) -> str:
    kind = term.kind
    cases = [logic.case(case_id) for case_id in term.case_ids]
    if kind is GuardKind.IN_CASE and term.decision_id:
        return f"{term.decision_id} = {' or '.join(case_short(case) for case in cases)}"
    if kind is GuardKind.NOT_CASES and term.decision_id:
        named = " or ".join(f"{case.id} ({case_short(case)})" for case in cases)
        verb = "leaves" if len(cases) == 1 else "leave"
        return f"{term.decision_id} did not take {named}, which always {verb}"
    steps = " and ".join(logic.step_text[step] for step in term.step_ids) or "an earlier step"
    if kind is GuardKind.ON_FAILURE_OF:
        if term.certainty is Certainty.POSSIBLE:
            # A MAP that succeeds does not always end an EXIT-ON SUCCESS sequence (S10).
            return f"{steps} failed, or did not end the sequence"
        return f"{steps} failed"
    if kind is GuardKind.ONLY_IF_SUCCEEDED:
        return f"{steps} succeeded"
    if kind is GuardKind.FINALLY:
        return (
            "after TRY and CATCH, whatever happened, unless EXIT `$flow` with failure left "
            f"({rule_label(['S33'])})"
        )
    if kind is GuardKind.PER_ITERATION:
        where = (
            f"once per element of {code_span(term.loop_path.text())}"
            if term.loop_path is not None
            else "once per iteration of the LOOP"
        )
        return f"{where}, until {_ids(term.exit_ids)} ends it" if term.exit_ids else where
    if kind is GuardKind.PER_ATTEMPT:
        text = "on each attempt of the REPEAT"
        return f"{text}, until {_ids(term.exit_ids)} ends it" if term.exit_ids else text
    if kind is GuardKind.MAY_BE_SKIPPED:
        return f"{_ids(term.exit_ids)} did not leave the enclosing step first"
    return "not analysed (nested too deeply)"


def certainty_text(guard: Guard, extra_rules: tuple[str, ...] = ()) -> str:
    label = assumption_label(sort_rules((*guard.rules, *extra_rules)))
    return f"{guard.certainty.value} ({label})" if label else guard.certainty.value


def _calls_block(logic: FlowLogic) -> str:
    lines = [
        "### Calls by condition",
        "",
        "| Call | Service | How | Runs when | Certainty |",
        "| --- | --- | --- | --- | --- |",
    ]
    for call in logic.calls[:MAX_CALL_ROWS]:
        lines.append(
            f"| {call.id} | {code_span(call.target)} | {_how(call)} | "
            f"{_cell(_runs_when(logic, call))} | {_cell(_call_certainty(call))} |"
        )
    lines += _more(len(logic.calls), MAX_CALL_ROWS, "call", prefix="")
    return "\n".join(lines)


_NEVER_TEXT = {
    "duplicate_case": "never: its case repeats an earlier label",
    "ignored_label": "never: label expressions ignore the label of its case",
    "try_cannot_fail": "never: it is in a CATCH, and nothing in the TRY before it can fail",
    "flow_failure": (
        "never: it is in a FINALLY, and every way out of the blocks before it is EXIT `$flow` "
        "with failure, which skips FINALLY"
    ),
    "no_linked_outputs": "never: no output is linked to the pipeline, so it does not run",
}


def _runs_when(logic: FlowLogic, call: CallContext) -> str:
    if call.reach is Reach.UNREACHABLE:
        return _NEVER_TEXT.get(
            call.unreachable_reason or "",
            "never: an earlier step always leaves first, or its case never runs",
        )
    text = guard_text(logic, call.guard)
    if call.same_target_count:
        others = ", ".join(call.same_target_as)
        extra = call.same_target_count - len(call.same_target_as)
        if extra:
            others += f" and {extra} more"
        text += f" (the same service is also called as {others})"
    return text


def _call_certainty(call: CallContext) -> str:
    if call.reach is Reach.UNREACHABLE:
        label = assumption_label(call.unreachable_rules)
        return f"derived ({label})" if label else "derived"
    return certainty_text(call.guard)


def _how(call: CallContext) -> str:
    return "transformer" if call.call_type is CallType.MAPINVOKE else "step"


def _exits_block(logic: FlowLogic) -> str:
    lines = ["### Exits", ""]
    for item in logic.exits[:MAX_LIST_ROWS]:
        lines.append(f"- {exit_text(logic, item)}; runs when: {guard_text(logic, item.guard)}.")
    lines += _more(len(logic.exits), MAX_LIST_ROWS, "EXIT", prefix="")
    return "\n".join(lines)


def exit_text(logic: FlowLogic, item: ExitEffect) -> str:
    signal = _signal(item.signal)
    if item.target_id is None:
        reason = f" ({item.note})" if item.note else ""
        return f"{item.id} leaves a step that cannot be determined{reason}, with {signal}"
    if item.scope is ExitScope.ITERATION:
        text = (
            f"{item.id} ends the current iteration of {logic.step_text[item.target_id]} with "
            f"{signal}; the next iteration runs"
        )
    else:
        text = f"{item.id} leaves {logic.step_text[item.target_id]} with {signal}"
    if item.reach_id is not None and item.reach_id != item.target_id:
        text += f"; the failure ends {logic.step_text[item.reach_id]}"
    label = assumption_label(item.rules)
    return f"{text} ({label})" if label else text


def _unreachable_block(logic: FlowLogic) -> str:
    lines = ["### Steps that never run", ""]
    for item in logic.unreachable[:MAX_LIST_ROWS]:
        label = assumption_label(item.rules)
        suffix = f" ({label})" if label else ""
        step = logic.step_text[item.node_id]
        if item.reason == "duplicate_case":
            lines.append(f"- {item.case_id}: an earlier case has the same label{suffix}.")
        elif item.reason == "ignored_label":
            lines.append(
                f"- {item.case_id}: label expressions ignore a blank or `$null` label{suffix}."
            )
        elif item.reason == "try_cannot_fail":
            lines.append(f"- {step}: nothing in the TRY before it can fail{suffix}.")
        elif item.reason == "flow_failure":
            lines.append(
                f"- {step}: every way out of the blocks before it is EXIT `$flow` with failure "
                f"({_ids(item.exit_ids)}), which skips it{suffix}."
            )
        elif item.reason == "no_linked_outputs":
            lines.append(f"- {step}: no output is linked, so the transformer does not run{suffix}.")
        else:
            lines.append(f"- {step}: {_ids(item.exit_ids)} always leaves first{suffix}.")
    lines += _more(len(logic.unreachable), MAX_LIST_ROWS, "step", prefix="")
    return "\n".join(lines)


# --- helpers -------------------------------------------------------------------------------


def _call_ref(logic: FlowLogic, call_id: str) -> str:
    return f"{call_id} {code_span(logic.call(call_id).target)}"


# --- scenarios -----------------------------------------------------------------------------

SCENARIOS_INTRO = (
    "Decisions whose fields depend on an earlier decision are combined along that dependency, "
    f"at most {MAX_CHAIN} in a row; decisions that depend on no other one are never multiplied "
    "with each other. Each row takes one outcome per decision; cases that leave the same "
    "origins further on are grouped. A combination is ruled out only when the field has one "
    "observed literal on every path and a value label differs from it. Calls that also need "
    'another condition say so. "possible": values this service sets itself may lead there; '
    '"conditional": it also needs a value from the caller or a call\'s response; '
    '"unresolved": a field or condition is not followed.'
)
MAX_RULED_SHOWN = 20


def render_scenarios(logic: FlowLogic, scenarios: FlowScenarios) -> str:
    """The "### Scenarios" part of the Decisions section, or "" without combined decisions."""
    if not scenarios.tables:
        return ""
    lines = ["### Scenarios", "", SCENARIOS_INTRO]
    for table in scenarios.tables:
        if not table.scenarios:
            lines += [
                "",
                f"{', '.join(table.decision_ids)} depend on each other but are not combined: "
                "the limit on combinations followed per service was reached.",
            ]
            continue
        lines += ["", *_scenario_table(logic, table)]
    if scenarios.independent:
        lines += ["", f"Not combined with another decision: {', '.join(scenarios.independent)}."]
    if scenarios.in_loops:
        lines += [
            "",
            "Inside a loop, so each iteration may take another case; not combined: "
            f"{', '.join(scenarios.in_loops)}.",
        ]
    if scenarios.limits:
        lines += ["", "Scenario limits: " + "; ".join(scenarios.limits) + "."]
    return "\n".join(lines)


def _scenario_table(logic: FlowLogic, table: ScenarioTable) -> list[str]:
    lines = [
        f"#### {', '.join(table.decision_ids)}",
        "",
        "| # | Conditions | Calls, in order | Ends with | Depends on responses of | Feasibility |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for scenario in table.scenarios:
        calls = [_scenario_call(logic, table, scenario, call_id) for call_id in scenario.call_ids]
        depends = ", ".join(_call_ref(logic, call_id) for call_id in scenario.depends_on_calls)
        label = assumption_label(scenario.rules)
        feasibility = scenario.feasibility.value + (f" ({label})" if label else "")
        lines.append(
            f"| {scenario.id} | {_cell(_conditions(logic, scenario.outcomes))} | "
            f"{_cell(', '.join(calls)) or '-'} | {_cell(_scenario_end(logic, scenario))} | "
            f"{_cell(depends) or '-'} | {_cell(feasibility)} |"
        )
    if table.walk_limit:
        lines += [
            "",
            "Cut short: the limit on combinations followed per service was reached; further "
            "combinations are not shown.",
        ]
    elif table.truncated:
        lines += [
            "",
            f"Cut short: at most {MAX_SCENARIOS} scenarios are listed; further combinations "
            "are not shown.",
        ]
    if table.left_out:
        lines += [
            "",
            f"{', '.join(table.left_out)} also depend on these decisions and are not combined "
            f"(at most {MAX_CHAIN} in a row).",
        ]
    if table.ruled_out:
        lines += ["", "Ruled out:", ""]
        lines += [f"- {_ruled_text(logic, item)}" for item in table.ruled_out[:MAX_RULED_SHOWN]]
        hidden = len(table.ruled_out) - min(len(table.ruled_out), MAX_RULED_SHOWN)
        if hidden:
            lines.append(f"- and {hidden} more")
    return lines


def outcome_text(logic: FlowLogic, outcome: Outcome) -> str:
    decision = logic.decision(outcome.decision_id)
    if outcome.kind is OutcomeKind.NOT_REACHED:
        return f"{decision.id} is not reached"
    if outcome.kind is OutcomeKind.FAILS:
        field = code_span(decision.switch.text()) if decision.switch else "the switch value"
        return f"{decision.id} fails: {field} is missing ({rule_label(['S31'])})"
    names = [case_short(logic.case(case_id)) for case_id in outcome.case_ids]
    if not names:
        return f"{decision.id}: no case matches"
    text = f"{decision.id} = {' or '.join(names)}"
    return f"{text} or no case matches" if outcome.no_match else text


def _conditions(logic: FlowLogic, outcomes: tuple[Outcome, ...]) -> str:
    return "; ".join(outcome_text(logic, item) for item in outcomes)


def _scenario_call(
    logic: FlowLogic, table: ScenarioTable, scenario: Scenario, call_id: str
) -> str:
    """A call of a scenario, with what else it needs: cases of a grouped outcome, decisions
    outside the table, loops, failures."""
    call = logic.call(call_id)
    return _call_ref(logic, call_id) + _qualifiers(logic, table, scenario, call.guard, call.reach)


def _qualifiers(
    logic: FlowLogic,
    table: ScenarioTable,
    scenario: Scenario,
    guard: Guard,
    reach: Reach | None = None,
) -> str:
    text = ""
    for outcome in scenario.outcomes:
        if not outcome.grouped:
            continue
        for term in guard.terms:
            if term.kind is GuardKind.IN_CASE and term.decision_id == outcome.decision_id:
                cases = [case_short(logic.case(case_id)) for case_id in term.case_ids]
                text += f" (only when {outcome.decision_id} = {' or '.join(cases)})"
    others = [
        term_text(logic, term)
        for term in guard.terms
        if (
            term.kind in (GuardKind.IN_CASE, GuardKind.NOT_CASES)
            and term.decision_id not in table.decision_ids
        )
        or term.kind in (GuardKind.PER_ITERATION, GuardKind.PER_ATTEMPT)
    ]
    if others:
        text += f" (also only when {'; '.join(others)})"
    if reach is Reach.FAILURE_PATH:
        text += " (after a failure)"
    return text


def _scenario_end(logic: FlowLogic, scenario: Scenario) -> str:
    if scenario.fails_at is not None:
        text = f"{scenario.fails_at} fails ({rule_label(['S31'])}); "
        if scenario.service_fails:
            text += "the service fails"
        elif scenario.failure_end is None:
            text += "where the failure ends cannot be determined"
        else:
            text += (
                f"{logic.step_text[scenario.failure_end]} fails with it, and what handles that "
                "runs next (a CATCH, a later alternative or the rest of an EXIT-ON DONE "
                "sequence)"
            )
    elif scenario.ends:
        text = ", ".join(_exit_ref(logic, exit_id) for exit_id in scenario.ends)
        if any("S33" in logic.exit(exit_id).rules for exit_id in scenario.ends):
            text += f"; no CATCH or FINALLY runs ({rule_label(['S33'])})"
    elif scenario.after is not None:
        text = f"goes on after {scenario.after}"
    else:
        text = "-"
    for node_id, array in scenario.loop_failures:
        field = code_span(array) if array else "its array"
        text += (
            f"; or it fails instead if {field} is missing ({rule_label(['S29'])}), at "
            f"{logic.step_text[node_id]}"
        )
    return text


def _ruled_text(logic: FlowLogic, item: RuledOut) -> str:
    decision = logic.decision(item.decision_id)
    if item.case_id is None:
        what = f"no case of {decision.id} matches"
    else:
        what = f"{decision.id} = {case_short(logic.case(item.case_id))}"
    before = _conditions(logic, item.prefix)
    when = f"{before}; {what}" if before else what
    where = logic.step_text.get(item.node_id or "", "a step")
    return (
        f"{when}: {code_span(item.path)} is always {code_span(item.value)} there (set in "
        f"{where}) ({rule_label(['S2'])})"
    )


def _exit_ref(logic: FlowLogic, exit_id: str) -> str:
    item = logic.exit(exit_id)
    if item.target_id is None:
        return f"{exit_id} (target not determined)"
    if item.scope is ExitScope.ITERATION:
        return f"{exit_id} (ends the current iteration of {logic.step_text[item.target_id]})"
    return f"{exit_id} (leaves {logic.step_text[item.target_id]}, {_signal(item.signal)})"


def _signal(signal: str) -> str:
    return {"SUCCESS": "success", "FAILURE": "failure"}.get(signal, "an unknown signal")


def _ids(ids: tuple[str, ...]) -> str:
    shown = ", ".join(ids[:MAX_IDS])
    return shown + (f" and {len(ids) - MAX_IDS} more" if len(ids) > MAX_IDS else "")


def _more(total: int, shown: int, noun: str, prefix: str = "") -> list[str]:
    hidden = total - min(total, shown)
    return [f"{prefix}... and {hidden} more {noun}(s) not shown."] if hidden else []


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "\\|")
