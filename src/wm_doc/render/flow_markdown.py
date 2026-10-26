"""The "Decisions" section of a service page, from the derived control model (`flow_logic`).

Conditions are shown as written in the FLOW and never evaluated. Every row says how certain it
is; rows resting on an Integration Server rule not yet confirmed on 10.15 name the assumption.
Label text only ever appears flattened inside code spans, so it cannot form Markdown structure.
"""

from __future__ import annotations

from wm_doc.flow_logic import (
    CallContext,
    ConditionKind,
    Decision,
    DecisionCase,
    DecisionMode,
    ExitEffect,
    FlowLogic,
    Guard,
    GuardKind,
    GuardTerm,
    Reach,
    case_rules,
    code_span,
    sort_rules,
)
from wm_doc.flow_semantics import RULES, assumption_label
from wm_doc.ir import CallType

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

NOTE_TEXT = {
    "SWITCH_IGNORED": "It also names a switch, which label expressions are assumed to ignore.",
    "NO_SWITCH": "It has no switch and its labels are not expressions; IS behaviour is unknown.",
    "DEFAULT_NOT_LAST": (
        "`$default` is not the last case; it is assumed to run only when no other case "
        "matches (assumption S6)."
    ),
    "DUPLICATE_LABEL": "A case repeats an earlier label and never runs (S2).",
    "LABELS_WITHHELD": "Some case labels are withheld by the free-text policy.",
    "EXPRESSION_NOT_SPLIT": "Some label expressions could not be split into field references.",
}


def render_decisions_section(logic: FlowLogic | None) -> str:
    """The section body (without its heading), or "" when there is nothing conditional."""
    if logic is None or not logic.significant:
        return ""
    parts = [INTRO]
    parts += [_decision_block(logic, item) for item in logic.decisions[:MAX_DECISIONS_SHOWN]]
    parts += _more(len(logic.decisions), MAX_DECISIONS_SHOWN, "decision")
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


def _decision_block(logic: FlowLogic, decision: Decision) -> str:
    line = f" (line {decision.source.line})" if decision.source.line else ""
    if decision.mode is DecisionMode.EXPRESSIONS:
        title = f"### {decision.id}: BRANCH with label expressions{line}"
    elif decision.switch is not None:
        title = f"### {decision.id}: BRANCH on {code_span(decision.switch.text())}{line}"
    else:
        title = f"### {decision.id}: BRANCH without a switch{line}"
    lines = [title, ""]
    if decision.guard.terms:
        lines += [f"Evaluated only when: {guard_text(logic, decision.guard)}.", ""]
    if decision.loop_id is not None:
        lines += ["It is inside a loop, so each iteration may take a different case.", ""]
    for note in decision.notes:
        lines += [NOTE_TEXT.get(note, note), ""]
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
            label = assumption_label([case.unreachable_rule])
            notes.append(f"never runs ({label or case.unreachable_rule})")
        label = assumption_label(case_rules(decision.mode, case.condition.kind))
        if label:
            notes.append(label)
        lines.append(
            f"| {case.id} | {_cell(condition_text(decision, case))} | "
            f"{_cell(', '.join(calls)) or '-'} | {_cell(', '.join(ends)) or '-'} | "
            f"{_cell('; '.join(notes)) or '-'} |"
        )
    if decision.falls_through:
        lines.append(
            "| - | no case matches | - | - | nothing runs and the next step follows "
            "(assumption S7) |"
        )
    return "\n".join(lines)


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
        return f"{steps} failed"
    if kind is GuardKind.ONLY_IF_SUCCEEDED:
        return f"{steps} succeeded"
    if kind is GuardKind.FINALLY:
        return "after TRY and CATCH, whatever happened"
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


def _runs_when(logic: FlowLogic, call: CallContext) -> str:
    if call.reach is Reach.UNREACHABLE:
        return "never: an earlier step always leaves first, or its case never runs"
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
        if item.reason == "duplicate_case":
            lines.append(f"- {item.case_id}: an earlier case has the same label{suffix}.")
        else:
            step = logic.step_text[item.node_id]
            lines.append(f"- {step}: {_ids(item.exit_ids)} always leaves first{suffix}.")
    lines += _more(len(logic.unreachable), MAX_LIST_ROWS, "step", prefix="")
    return "\n".join(lines)


# --- helpers -------------------------------------------------------------------------------


def _call_ref(logic: FlowLogic, call_id: str) -> str:
    return f"{call_id} {code_span(logic.call(call_id).target)}"


def _exit_ref(logic: FlowLogic, exit_id: str) -> str:
    item = logic.exit(exit_id)
    if item.target_id is None:
        return f"{exit_id} (target not determined)"
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
