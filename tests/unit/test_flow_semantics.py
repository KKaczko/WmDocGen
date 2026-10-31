"""The FLOW semantics registry and its documentation stay in step."""

from __future__ import annotations

import re
from pathlib import Path

from wm_doc.flow_semantics import (
    RULES,
    RULES_BY_ID,
    RuleStatus,
    assumption_label,
    rule,
    rule_label,
)

DOC = Path(__file__).resolve().parents[2] / "docs" / "flow-semantics.md"
ROW_RE = re.compile(
    r"^\| (S\d+) \| ([^|]+) \| [^|]+ \| (documented|assumed|verified) \| ([^|]*)\| ([^|]*)\|$"
)
SOURCE_RE = re.compile(r"^\[(\d+)\]: (https://www\.ibm\.com/docs/\S+)$", re.MULTILINE)


def _rows() -> dict[str, tuple[str, RuleStatus, tuple[str, ...], tuple[str, ...]]]:
    rows = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        match = ROW_RE.match(line)
        if match:
            checks = tuple(item.strip() for item in match.group(4).split(",") if item.strip())
            sources = tuple(re.findall(r"\[(\d+)\]", match.group(5)))
            rows[match.group(1)] = (
                match.group(2).strip(),
                RuleStatus(match.group(3)),
                checks,
                sources,
            )
    return rows


def test_rule_ids_are_unique_and_numbered_in_order() -> None:
    ids = [item.id for item in RULES]

    assert ids == [f"S{number}" for number in range(1, len(ids) + 1)]
    assert set(RULES_BY_ID) == set(ids)


def test_every_rule_appears_in_the_document_with_the_same_status_and_checks() -> None:
    rows = _rows()

    assert set(rows) == set(RULES_BY_ID)
    for item in RULES:
        assert rows[item.id][:3] == (item.topic, item.status, item.checks), item.id


def test_every_rule_cites_an_ibm_source_that_is_defined() -> None:
    defined = dict(SOURCE_RE.findall(DOC.read_text(encoding="utf-8")))

    for rule_id, (_topic, _status, _checks, sources) in _rows().items():
        assert sources, rule_id
        assert all(source in defined for source in sources), rule_id


def test_every_check_is_described_in_the_checklist() -> None:
    text = DOC.read_text(encoding="utf-8")
    checks = sorted({check for item in RULES for check in item.checks}, key=lambda c: int(c[1:]))

    assert checks == [f"V{number}" for number in range(1, len(checks) + 1)]
    assert len(checks) == 34
    for check in checks:
        assert f"\n| {check} | " in text, check


def test_no_rule_is_verified_before_the_owner_checks() -> None:
    assert all(item.status is not RuleStatus.VERIFIED for item in RULES)


def test_assumption_label_lists_only_assumed_rules_in_order() -> None:
    assert rule("S14").assumed
    assert not rule("S1").assumed

    assert assumption_label(["S1", "S2"]) is None
    assert assumption_label(["S37", "S1", "S14", "S37"]) == "assumption S14, S37"


def test_rule_label_names_plain_rules_and_assumptions() -> None:
    assert rule_label(["S7"]) == "S7"
    assert rule_label(["S37", "S2"]) == "S2; assumption S37"
    assert rule_label(["S19", "S14"]) == "assumption S14, S19"
