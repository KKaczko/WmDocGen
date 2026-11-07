"""Detailed-flow items a fake model answer can return, read from a describe prompt (test-only).

Since stage 4 of the conditional-flow work, a detailed flow is a list of items that reference
the call and case ids shown in the prompt (`[C3] CALL x`, `[D1.c2] when "A":`). These helpers
build items that pass the checks: one item per call, in the innermost case it runs in.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

_CALL_RE = re.compile(r"^(\s*)\[(C\d+)\] (?:CALL|TRANSFORM via) (\S+)")
_CASE_RE = re.compile(r"^(\s*)\[(D\d+\.c\d+)\] ")


def prompt_calls(prompt: str) -> list[tuple[str, str, str]]:
    """(call id, target, innermost case id or "") for every call line of the prompt."""
    found: list[tuple[str, str, str]] = []
    stack: list[tuple[int, str]] = []
    for line in prompt.splitlines():
        indent = len(line) - len(line.lstrip())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        case = _CASE_RE.match(line)
        if case:
            stack.append((indent, case.group(2)))
            continue
        call = _CALL_RE.match(line)
        if call:
            found.append((call.group(2), call.group(3), stack[-1][1] if stack else ""))
    return found


def call_id(prompt: str, target: str) -> str:
    """The id of the first call to `target` in the prompt."""
    return next(found for found, name, _case in prompt_calls(prompt) if name == target)


def item(text: str, *calls: str, case: str = "") -> dict[str, Any]:
    decision = case.split(".", 1)[0] if case else ""
    return {"text": text, "decision": decision, "case": case, "calls": list(calls)}


def flow_items(
    prompt: str, text: Callable[[str], str] = lambda target: f"Calls `{target}`."
) -> list[dict[str, Any]]:
    """One item per call of the prompt, in the case it runs in."""
    return [item(text(target), found, case=case) for found, target, case in prompt_calls(prompt)]
