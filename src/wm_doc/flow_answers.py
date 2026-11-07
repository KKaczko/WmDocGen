"""The detailed flow of a description as structured items, checked against the control model.

Stage 4 of the conditional-flow work. The model returns each detailed-flow item as text plus
the ids it is about: the decision (`D1`), the case whose steps it describes (`D1.c2`) and the
calls it describes (`C3`). The tool, not the model, writes the condition of a case in front
of the text, so a condition is never paraphrased or invented. Before an answer is accepted
the items are checked against the facts (`flow_logic`):

- R1: every id exists, and a case belongs to the decision the item names.
- R2: a call or EXIT sits in an item about the innermost case it runs in (or about no case).
- R3: every call that matters is listed by some item; one item does not mix calls that run
  only after a failure with calls that run otherwise.
- R4: every decision that decides something (its cases call services or leave) has an item.
- R5: a quoted or all-capitals value in the text occurs in the facts.
- R6: an item about a call that runs only under a condition does not say it always runs.
- R7: the text does not name a call that runs only in another case than the item's.

Only calls and decisions whose ids the prompt shows are required (R3, R4). Ids the model
writes are normalised (`[c3]` is `C3`), read by their shape (`flow_item`: small models put
case and EXIT ids into `calls`) and echoed in corrections only in the shape of an id.

`standard` enforces R1-R3; `thorough` and `deep` enforce all; rules not enforced are only
counted. A failed check shares the one corrective retry of the answer.

`logic_json` is the canonical form of the control model hashed into description files with
facts basis 2. It carries behaviour only (decisions, cases, calls, exits and the conditions
they run under), never a rule id, a rule status or an assumption label, so confirming a rule
on IS 10.15 never marks an approved description as changed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from enum import StrEnum

from wm_doc.flow_logic import (
    CallContext,
    Decision,
    DecisionCase,
    DecisionMode,
    ExitEffect,
    FlowLogic,
    GuardKind,
    GuardTerm,
    Reach,
)
from wm_doc.render.flow_markdown import case_short, code_span, condition_text, guard_text

MAX_ITEM_CALLS = 12
MAX_SIGNIFICANT = 10  # decisions R4 asks an item for
MAX_PROMPT_DECISIONS = 30
MAX_PROMPT_CALL_LINES = 40
MAX_VIOLATIONS_SHOWN = 8
MAX_ID_CHARS = 12

_ID_TOKEN_RE = re.compile(r"\[(?:D\d+(?:\.c\d+)?|C\d+|E\d+)\]\s*")
_ID_SHAPE_RE = re.compile(r"D\d{1,4}(?:\.c\d{1,4})?|C\d{1,5}|E\d{1,4}")
_ID_LOOSE_RE = re.compile(
    r"\[?\s*([dce])\s*(\d{1,5})(?:\s*\.\s*c\s*(\d{1,4}))?\s*\]?\.?", re.IGNORECASE
)
_CASE_ID_RE = re.compile(r"D\d+\.c\d+")
_DECISION_ID_RE = re.compile(r"D\d+")
_EXIT_ID_RE = re.compile(r"E\d+")
_SHOWN_ID_RE = re.compile(r"(?<![\w.])(D\d+(?:\.c\d+)?|C\d+|E\d+)(?!\w)")
_QUOTED_RE = re.compile(r"\"([^\"\n]{1,80})\"|“([^”\n]{1,80})”")
_CAPS_RE = re.compile(r"(?<![\w$/.:`])[A-Z][A-Z0-9_]+(?![\w$])")
_ALWAYS_RE = re.compile(
    r"\b(always|unconditionally|regardless|in (?:all|every) cases?|in any case)\b",
    re.IGNORECASE,
)
# Guards that make a call conditional; a LOOP, REPEAT or FINALLY alone does not.
_CONDITION_GUARDS = frozenset(
    {
        GuardKind.IN_CASE,
        GuardKind.NOT_CASES,
        GuardKind.ON_FAILURE_OF,
        GuardKind.ONLY_IF_SUCCEEDED,
        GuardKind.MAY_BE_SKIPPED,
    }
)
# Words a description uses for FLOW structure and common formats, never condition values.
_CAPS_ALLOWED = frozenset(
    {
        "BRANCH", "LOOP", "REPEAT", "MAP", "EXIT", "TRY", "CATCH", "FINALLY", "SEQUENCE",
        "CALL", "TRANSFORM", "SUCCESS", "FAILURE", "DONE", "FLOW", "JSON", "XML", "HTTP",
        "HTTPS", "SQL", "ID", "IDS", "API", "URL", "URI", "REST", "SOAP", "JDBC", "JMS", "FTP",
        "SFTP", "CSV", "PDF", "UTF", "IS", "IO", "UUID", "DB", "ERP", "CRM", "UI",
        "NULL", "TRUE", "FALSE", "AND", "OR", "NOT", "IF", "GET", "POST", "PUT", "PATCH",
        "DELETE", "HEAD", "HTML", "XSLT", "WSDL", "SMTP", "TLS", "SSL", "MQ", "EDI", "ASCII",
        "EOF", "ZIP", "YAML",
    }
)  # fmt: skip


class FlowRule(StrEnum):
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"
    R5 = "R5"
    R6 = "R6"
    R7 = "R7"


STANDARD_RULES = frozenset({FlowRule.R1, FlowRule.R2, FlowRule.R3})
ALL_RULES = frozenset(FlowRule)


@dataclass(frozen=True, slots=True)
class FlowItem:
    """One detailed-flow item as the model returns it."""

    text: str
    decision: str = ""
    case: str = ""
    calls: tuple[str, ...] = ()
    exits: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Violation:
    rule: FlowRule
    message: str


# --- reading -------------------------------------------------------------------------------


def normalize_id(value: object) -> str:
    """An id as the model wrote it, in the form the facts use: `[c3]` and `C3.` are `C3`."""
    text = str(value if value is not None else "").strip()
    match = _ID_LOOSE_RE.fullmatch(text)
    if match is None:
        return text[: MAX_ID_CHARS + 1]  # never a valid id; reported without echoing it
    letter, number, case = match.groups()
    found = f"{letter.upper()}{int(number)}"
    return f"{found}.c{int(case)}" if case is not None else found


def flow_item(text: str, decision: object, case: object, refs: Iterable[object]) -> FlowItem:
    """An item from the model's fields, each id in `calls` read by its shape.

    An EXIT id is an EXIT the item describes. A case or decision id fills an empty `case` or
    `decision`, or is dropped when it repeats it; any other one stays and is reported (R1).
    """
    decision_id = normalize_id(decision)
    case_id = normalize_id(case)
    calls: list[str] = []
    exits: list[str] = []
    for ref in refs:
        found = normalize_id(ref)
        if not found:
            continue
        if _EXIT_ID_RE.fullmatch(found):
            exits.append(found)
        elif _CASE_ID_RE.fullmatch(found) and case_id in ("", found):
            case_id = found
        elif _DECISION_ID_RE.fullmatch(found) and decision_id in ("", found):
            decision_id = found
        else:
            calls.append(found)
    return FlowItem(
        text,
        decision_id,
        case_id,
        tuple(dict.fromkeys(calls))[:MAX_ITEM_CALLS],
        tuple(dict.fromkeys(exits))[:MAX_ITEM_CALLS],
    )


def _not_a_call(value: str) -> str:
    if _CASE_ID_RE.fullmatch(value):
        return f"{value} is a case id, not a call id; one item describes one case, given in case"
    if _DECISION_ID_RE.fullmatch(value):
        return f"{value} is a decision id, not a call id; give it in decision"
    return f"{_echo(value)} is not a call id"


def _echo(value: str) -> str:
    """An id the model wrote, repeated only when it has the shape of an id."""
    return value if _ID_SHAPE_RE.fullmatch(value) else "an id that is not in the facts"


def strip_ids(text: str) -> str:
    """The text without `[D1]`, `[D1.c2]`, `[C3]` or `[E1]` tokens copied from the facts."""
    return " ".join(_ID_TOKEN_RE.sub("", text).split())


def item_text(item: FlowItem, logic: FlowLogic | None) -> str:
    """The item as stored in a description: the tool's condition, then the model's text."""
    text = strip_ids(item.text)
    if logic is None:
        return text
    case = _case(logic, item.case)
    if case is not None:
        owner = logic.decision(case.id.split(".", 1)[0])
        return f"When {condition_text(owner, case)} ({owner.id}): {text}"
    decision = _decision(logic, item.decision)
    if decision is not None:
        return f"At {_branch_name(decision)} ({decision.id}): {text}"
    return text


def _branch_name(decision: Decision) -> str:
    if decision.mode is DecisionMode.EXPRESSIONS:
        return "the BRANCH with label expressions"
    if decision.switch is not None:
        return f"the BRANCH on {code_span(decision.switch.text())}"
    return "the BRANCH without a switch"


def _decision(logic: FlowLogic, decision_id: str) -> Decision | None:
    try:
        return logic.decision(decision_id) if decision_id else None
    except KeyError:
        return None


def _case(logic: FlowLogic, case_id: str) -> DecisionCase | None:
    try:
        return logic.case(case_id) if case_id else None
    except KeyError:
        return None


def _call(logic: FlowLogic, call_id: str) -> CallContext | None:
    try:
        return logic.call(call_id)
    except KeyError:
        return None


def _exit(logic: FlowLogic, exit_id: str) -> ExitEffect | None:
    try:
        return logic.exit(exit_id)
    except KeyError:
        return None


# --- checks --------------------------------------------------------------------------------


def coverage_call_ids(logic: FlowLogic, targets: Collection[str]) -> tuple[str, ...]:
    """Calls a complete detailed flow lists: those to the coverage targets that can run."""
    wanted = set(targets)
    return tuple(
        call.id
        for call in logic.calls
        if call.target in wanted and call.reach is not Reach.UNREACHABLE
    )


def check_items(
    items: Iterable[FlowItem],
    logic: FlowLogic,
    coverage: Collection[str],
    facts: str,
) -> list[Violation]:
    """Every way the items disagree with the facts, in rule order."""
    items = list(items)
    shown = set(_SHOWN_ID_RE.findall(facts))  # a call cut from the prompt cannot be required
    found: list[Violation] = []
    listed: set[str] = set()
    for number, item in enumerate(items, 1):
        found += _references(logic, number, item)
        calls = [call for call_id in item.calls if (call := _call(logic, call_id)) is not None]
        exits = [step for exit_id in item.exits if (step := _exit(logic, exit_id)) is not None]
        listed.update(call.id for call in calls)
        found += _placement(logic, number, item, calls, exits)
        found += _wording(logic, number, item, calls, facts)
    for call_id in coverage:
        if call_id not in listed and call_id in shown:
            target = logic.call(call_id).target
            found.append(
                Violation(
                    FlowRule.R3,
                    f"no item lists call {call_id} ({code_span(target)}); add it where it runs",
                )
            )
    covered = {item.decision for item in items if item.decision}
    covered |= {item.case.split(".", 1)[0] for item in items if item.case}
    for decision in significant_decisions(logic):
        if decision.id not in covered and decision.id in shown:
            found.append(
                Violation(
                    FlowRule.R4,
                    f"no item is about decision {decision.id} ({_branch_name(decision)}); "
                    "add one",
                )
            )
    order = list(FlowRule)
    return sorted(found, key=lambda item: order.index(item.rule))


def _references(logic: FlowLogic, number: int, item: FlowItem) -> list[Violation]:
    found: list[Violation] = []
    decision = _decision(logic, item.decision)
    if item.decision and decision is None:
        found.append(
            Violation(FlowRule.R1, f"item {number}: {_echo(item.decision)} is not a decision id")
        )
    case = _case(logic, item.case)
    if item.case and case is None:
        found.append(
            Violation(FlowRule.R1, f"item {number}: {_echo(item.case)} is not a case id")
        )
    if case is not None and decision is not None and not case.id.startswith(f"{decision.id}."):
        found.append(
            Violation(
                FlowRule.R1, f"item {number}: case {case.id} does not belong to {decision.id}"
            )
        )
    for call_id in item.calls:
        if _call(logic, call_id) is None:
            found.append(Violation(FlowRule.R1, f"item {number}: {_not_a_call(call_id)}"))
    for exit_id in item.exits:
        if _exit(logic, exit_id) is None:
            found.append(Violation(FlowRule.R1, f"item {number}: {exit_id} is not an EXIT id"))
    return found


def _innermost_case(step: CallContext | ExitEffect) -> GuardTerm | None:
    terms = [term for term in step.guard.terms if term.kind is GuardKind.IN_CASE]
    return terms[-1] if terms else None


def _placement(
    logic: FlowLogic,
    number: int,
    item: FlowItem,
    calls: list[CallContext],
    exits: list[ExitEffect],
) -> list[Violation]:
    found: list[Violation] = []
    case_text = _echo(item.case)
    steps: list[CallContext | ExitEffect] = [*calls, *exits]
    for call in steps:
        term = _innermost_case(call)
        if term is None:
            if item.case:
                found.append(
                    Violation(
                        FlowRule.R2,
                        f"item {number}: {call.id} does not run inside a case, so it does not "
                        f"belong to {case_text}; list it in an item whose case is empty",
                    )
                )
            continue
        if item.case not in term.case_ids:
            cases = " or ".join(term.case_ids)
            when = " or ".join(case_short(logic.case(case_id)) for case_id in term.case_ids)
            found.append(
                Violation(
                    FlowRule.R2,
                    f"item {number}: {call.id} runs only when {term.decision_id} = {when}; "
                    f"list it in an item whose case is {cases}",
                )
            )
    failure = [call.id for call in calls if call.reach is Reach.FAILURE_PATH]
    normal = [call.id for call in calls if call.reach is not Reach.FAILURE_PATH]
    if failure and normal:
        found.append(
            Violation(
                FlowRule.R3,
                f"item {number} mixes calls that run only after a failure "
                f"({', '.join(failure)}) with calls that run otherwise ({', '.join(normal)}); "
                "split it",
            )
        )
    return found


def _wording(
    logic: FlowLogic, number: int, item: FlowItem, calls: list[CallContext], facts: str
) -> list[Violation]:
    found: list[Violation] = []
    text = item.text
    for match in _QUOTED_RE.finditer(text):
        value = match.group(1) or match.group(2) or ""
        if value.strip() and value not in facts:
            found.append(
                Violation(
                    FlowRule.R5,
                    f'item {number} names the value "{value}", which is not in the facts',
                )
            )
    for match in _CAPS_RE.finditer(text):
        word = match.group(0)
        if word in _CAPS_ALLOWED or re.search(rf"(?<![\w$]){re.escape(word)}(?![\w$])", facts):
            continue
        found.append(
            Violation(
                FlowRule.R5, f"item {number} names the value {word}, which is not in the facts"
            )
        )
    guarded = [
        call.id
        for call in calls
        if any(term.kind in _CONDITION_GUARDS for term in call.guard.terms)
    ]
    if (guarded or item.case) and _ALWAYS_RE.search(text):
        what = ", ".join(guarded) if guarded else f"the steps of {_echo(item.case)}"
        found.append(
            Violation(
                FlowRule.R6,
                f"item {number} says something always runs, but {what} run only under "
                "conditions; do not say always",
            )
        )
    # Naming a later call that uses a result is fine; naming one that runs only in another
    # case attributes it to the wrong condition.
    listed = {call.target for call in calls}
    for call in logic.calls:
        term = _innermost_case(call)
        if call.target in listed or term is None or item.case in term.case_ids:
            continue
        short = call.target.rsplit(":", 1)[-1]
        named = re.search(rf"(?<![\w.:$/]){re.escape(call.target)}(?![\w$])", text)
        if named or f"`{short}`" in text:
            when = " or ".join(case_short(logic.case(case_id)) for case_id in term.case_ids)
            found.append(
                Violation(
                    FlowRule.R7,
                    f"item {number} names {code_span(call.target)}, but {call.id} runs only "
                    f"when {term.decision_id} = {when}; describe it in its own item",
                )
            )
            listed.add(call.target)
    return found


def significant_decisions(logic: FlowLogic) -> list[Decision]:
    """Decisions whose cases call services that can run, or leave; the first few."""
    found: list[Decision] = []
    for decision in logic.decisions:
        decides = any(
            case.ends_with
            or any(logic.call(call_id).reach is not Reach.UNREACHABLE for call_id in case.call_ids)
            for case in decision.cases
            if case.unreachable_rule is None
        )
        if decides:
            found.append(decision)
        if len(found) >= MAX_SIGNIFICANT:
            break
    return found


def correction_prompt(problems: list[str]) -> str:
    """The corrective request for an answer whose detailed flow does not match the facts."""
    shown = problems[:MAX_VIOLATIONS_SHOWN]
    lines = "\n".join(f"- {item}" for item in shown)
    more = len(problems) - len(shown)
    tail = f"\n- and {more} more" if more else ""
    return (
        "Your detailed_steps do not match the facts:\n"
        f"{lines}{tail}\n"
        "Return the complete JSON again. In detailed_steps, give each item the ids it is about "
        "(decision, case, calls), list every call where it runs, and use only names and values "
        "that appear in the facts."
    )


# --- the prompt ----------------------------------------------------------------------------


def decisions_block(logic: FlowLogic) -> str:
    """The decisions and their cases with the calls in each, for the model to reference."""
    if not logic.decisions and not logic.calls:
        return ""
    lines = [
        "decisions (ids for detailed_steps; conditions as written, the tool adds them to the "
        "text):"
    ]
    for decision in logic.decisions[:MAX_PROMPT_DECISIONS]:
        head = f"  {decision.id} {_branch_name(decision).removeprefix('the ')}"
        if decision.guard.terms:
            head += f" (only when {guard_text(logic, decision.guard)})"
        lines.append(head + ":")
        for case in decision.cases:
            calls = ", ".join(case.call_ids) or "no calls"
            ends = f"; then {', '.join(case.ends_with)} leaves" if case.ends_with else ""
            never = " (never runs)" if case.unreachable_rule else ""
            lines.append(f"    {case.id} {condition_text(decision, case)}{never}: {calls}{ends}")
        if decision.falls_through:
            text = "    no case matches: nothing runs"
            if decision.missing_fails:
                field = code_span(decision.switch.text()) if decision.switch else "the switch"
                text += f", or the BRANCH fails if {field} is missing"
            lines.append(text)
    hidden = len(logic.decisions) - min(len(logic.decisions), MAX_PROMPT_DECISIONS)
    if hidden:
        lines.append(f"  ... and {hidden} more decision(s)")
    others = [call for call in logic.calls if call.guard.terms and _innermost_case(call) is None]
    if others:
        lines.append("other calls with conditions:")
        for call in others[:MAX_PROMPT_CALL_LINES]:
            when = "never" if call.reach is Reach.UNREACHABLE else guard_text(logic, call.guard)
            lines.append(f"  {call.id} {code_span(call.target)}: {when}")
        hidden = len(others) - min(len(others), MAX_PROMPT_CALL_LINES)
        if hidden:
            lines.append(f"  ... and {hidden} more call(s)")
    return "\n".join(lines)


# --- the facts hash ------------------------------------------------------------------------


def logic_json(logic: FlowLogic | None) -> str:
    """The control model as canonical JSON: behaviour only, never rules or their status."""
    if logic is None:
        return "null"

    def terms(items: Iterable[GuardTerm]) -> list[list[object]]:
        return [
            [
                term.kind.value,
                term.decision_id,
                list(term.case_ids),
                list(term.step_ids),
                list(term.exit_ids),
                term.loop_path.text() if term.loop_path is not None else None,
            ]
            for term in items
        ]

    payload = {
        "decisions": [
            {
                "id": decision.id,
                "mode": decision.mode.value,
                "switch": decision.switch.text() if decision.switch is not None else None,
                "guard": terms(decision.guard.terms),
                "falls_through": decision.falls_through,
                "missing_fails": decision.missing_fails,
                "cases": [
                    {
                        "id": case.id,
                        "kind": case.condition.kind.value,
                        "label": case.condition.text,
                        "excludes": list(case.excludes),
                        "never": case.unreachable_rule is not None,
                        "ends": list(case.ends_with),
                        "calls": list(case.call_ids),
                    }
                    for case in decision.cases
                ],
            }
            for decision in logic.decisions
        ],
        "calls": [
            {
                "id": call.id,
                "target": call.target,
                "reach": call.reach.value,
                "guard": terms(call.guard.terms),
            }
            for call in logic.calls
        ],
        "exits": [
            {
                "id": item.id,
                "scope": item.scope.value,
                "signal": item.signal,
                "target": item.target_id,
                "reach": item.reach_id,
            }
            for item in logic.exits
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
