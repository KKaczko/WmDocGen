"""The FLOW semantics registry and its documentation stay in step."""

from __future__ import annotations

import re
from pathlib import Path

from wm_doc.flow_semantics import RULES, RULES_BY_ID, RuleStatus, assumption_label, rule

DOC = Path(__file__).resolve().parents[2] / "docs" / "flow-semantics.md"
ROW_RE = re.compile(
    r"^\| (S\d+) \| ([^|]+) \| [^|]+ \| (documented|assumed|verified) \| ([^|]*)\|$"
)


def test_rule_ids_are_unique_and_numbered_in_order() -> None:
    ids = [item.id for item in RULES]

    assert ids == [f"S{number}" for number in range(1, len(ids) + 1)]
    assert set(RULES_BY_ID) == set(ids)


def test_every_rule_appears_in_the_document_with_the_same_status_and_checks() -> None:
    rows = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        match = ROW_RE.match(line)
        if match:
            checks = tuple(item.strip() for item in match.group(4).split(",") if item.strip())
            rows[match.group(1)] = (match.group(2).strip(), RuleStatus(match.group(3)), checks)

    assert set(rows) == set(RULES_BY_ID)
    for item in RULES:
        assert rows[item.id] == (item.topic, item.status, item.checks), item.id


def test_every_check_is_described_in_the_checklist() -> None:
    text = DOC.read_text(encoding="utf-8")
    checks = sorted({check for item in RULES for check in item.checks}, key=lambda c: int(c[1:]))

    assert checks == [f"V{number}" for number in range(1, len(checks) + 1)]
    assert len(checks) == 26
    for check in checks:
        assert f"\n| {check} | " in text, check


def test_assumption_label_lists_only_assumed_rules_in_order() -> None:
    assert rule("S4").assumed
    assert not rule("S1").assumed

    assert assumption_label(["S1", "S2"]) is None
    assert assumption_label(["S7", "S1", "S4", "S7"]) == "assumption S4, S7"
