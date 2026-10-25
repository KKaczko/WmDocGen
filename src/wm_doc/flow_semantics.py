"""Integration Server FLOW behaviour that the conditional-flow analysis relies on.

Static analysis cannot run a service, so every conclusion about which step runs when rests on
Integration Server behaviour. Each rule here has an id that derived facts cite and a status:

- DOCUMENTED: described in the webMethods FLOW documentation; relied on without a label.
- ASSUMED: plausible but not confirmed for IS 10.15; conclusions that rest on it are shown to
  readers as assumptions.
- VERIFIED: confirmed by the repository owner on IS 10.15 with the test services described in
  `docs/flow-semantics.md`.

After a check, change the rule here and its row in `docs/flow-semantics.md`; a test keeps the
two in step.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class RuleStatus(StrEnum):
    DOCUMENTED = "documented"
    ASSUMED = "assumed"
    VERIFIED = "verified"


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    topic: str
    statement: str
    status: RuleStatus
    # Items of the owner checklist in docs/flow-semantics.md that confirm or refine the rule.
    checks: tuple[str, ...] = ()

    @property
    def assumed(self) -> bool:
        return self.status is RuleStatus.ASSUMED


DOCUMENTED = RuleStatus.DOCUMENTED
ASSUMED = RuleStatus.ASSUMED

RULES: tuple[Rule, ...] = (
    Rule(
        "S1", "BRANCH", "One evaluation of a BRANCH runs at most one of its children.", DOCUMENTED
    ),
    Rule(
        "S2",
        "BRANCH",
        "With a switch, a child runs when its label equals the switch value as an exact, "
        "case-sensitive string; the first matching child in document order wins.",
        DOCUMENTED,
        ("V1",),
    ),
    Rule(
        "S3",
        "BRANCH",
        "The label $null matches when the switch variable is missing or null.",
        DOCUMENTED,
        ("V2",),
    ),
    Rule("S4", "BRANCH", "A blank label matches an empty-string switch value.", ASSUMED, ("V3",)),
    Rule(
        "S5",
        "BRANCH",
        "A label written between slashes (/.../) is a regular expression matched against the "
        "switch value.",
        ASSUMED,
        ("V4",),
    ),
    Rule(
        "S6",
        "BRANCH",
        "The $default child runs only when no other child matched, wherever it is placed.",
        ASSUMED,
        ("V5",),
    ),
    Rule(
        "S7",
        "BRANCH",
        "When no child matches and there is no $default child, the BRANCH does nothing and "
        "succeeds; the next step runs.",
        ASSUMED,
        ("V6",),
    ),
    Rule(
        "S8",
        "BRANCH",
        "With label expressions, the children's labels are evaluated in document order and the "
        "first one that is true wins; a later child runs only when every earlier one is false.",
        DOCUMENTED,
        ("V7",),
    ),
    Rule(
        "S9",
        "BRANCH",
        "A switch value that is not a string is compared by its string form.",
        ASSUMED,
        ("V8",),
    ),
    Rule(
        "S10",
        "SEQUENCE",
        "EXIT-ON FAILURE stops at the first child that fails and fails; EXIT-ON SUCCESS stops "
        "at the first child that succeeds; EXIT-ON DONE runs every child whatever happens.",
        DOCUMENTED,
        ("V9",),
    ),
    Rule(
        "S11",
        "EXIT",
        "EXIT leaves the parent step ($parent), the innermost LOOP or REPEAT ($loop), the whole "
        "service ($flow) or the nearest enclosing step with the given label, with SUCCESS or "
        "FAILURE.",
        DOCUMENTED,
        ("V10", "V11"),
    ),
    Rule(
        "S12",
        "EXIT",
        "Exiting a LOOP ends the whole loop, not only the current iteration.",
        DOCUMENTED,
    ),
    Rule(
        "S13",
        "TRY/CATCH",
        "A failure or an EXIT with FAILURE inside TRY runs CATCH; FINALLY runs after TRY and "
        "CATCH whatever happened, including after an EXIT.",
        ASSUMED,
        ("V12",),
    ),
    Rule(
        "S14",
        "TRY/CATCH",
        "IS 10.15 writes TRY and CATCH (and FINALLY) as sibling SEQUENCE steps with a FORM "
        "attribute inside a SEQUENCE with EXIT-ON SUCCESS; older services write the same idea "
        "as an EXIT-ON SUCCESS SEQUENCE without FORM.",
        ASSUMED,
        ("V13", "V25"),
    ),
    Rule(
        "S15",
        "Pipeline",
        "Pipeline changes a step made before it failed stay in the pipeline (they are not "
        "rolled back) when a CATCH, an EXIT-ON SUCCESS sequence or a REPEAT continues.",
        ASSUMED,
        ("V14",),
    ),
    Rule(
        "S16",
        "INVOKE",
        "An invoked service works on the caller's pipeline: whatever it leaves there, declared "
        "as output or not, is visible after the call.",
        DOCUMENTED,
        ("V24",),
    ),
    Rule(
        "S17",
        "INVOKE",
        "Values written by an INVOKE step's input map stay in the pipeline after the call "
        "unless they are dropped.",
        ASSUMED,
        ("V15",),
    ),
    Rule(
        "S18",
        "Transformer",
        "A transformer only sees what its input map gives it, and only the outputs its output "
        "map copies reach the pipeline.",
        DOCUMENTED,
    ),
    Rule(
        "S19",
        "MAP",
        "The order in which one MAP step applies its copies, sets and drops: assumed to read "
        "every source before writing any target, with drops last.",
        ASSUMED,
        ("V16",),
    ),
    Rule(
        "S20",
        "MAP",
        "A copy whose source is absent leaves the target unchanged.",
        ASSUMED,
        ("V17",),
    ),
    Rule(
        "S21",
        "MAP",
        "A set with overwrite off only sets a missing value; a set with variable substitution "
        "replaces %name% references with pipeline values (global variable substitution uses "
        "global variables).",
        DOCUMENTED,
        ("V18",),
    ),
    Rule(
        "S22",
        "LOOP",
        "Inside a LOOP, the IN-ARRAY path names the current element; the OUT-ARRAY collects "
        "one value per iteration.",
        DOCUMENTED,
        ("V19",),
    ),
    Rule(
        "S23",
        "REPEAT",
        "REPEAT runs its children again on the chosen condition up to COUNT more times "
        "(-1 without limit), waiting BACK-OFF seconds between attempts.",
        ASSUMED,
        ("V20",),
    ),
    Rule(
        "S24",
        "Scope",
        "A step with a scope works on the fields of one document instead of the whole pipeline.",
        ASSUMED,
        ("V21",),
    ),
    Rule(
        "S25",
        "MAP",
        "A copy can carry a condition that decides at run time whether it is applied.",
        ASSUMED,
        ("V22",),
    ),
    Rule(
        "S26",
        "Pipeline",
        "pub.flow:clearPipeline removes every field except the preserved ones.",
        DOCUMENTED,
    ),
    Rule(
        "S27",
        "Pipeline",
        "pub.flow:restorePipeline and pub.flow:restorePipelineFromFile put saved values back "
        "into the pipeline; whether they replace it or merge into it is not confirmed.",
        ASSUMED,
        ("V23",),
    ),
    Rule(
        "S28",
        "BRANCH",
        "Any step can be a child of a BRANCH; its NAME is the case label.",
        DOCUMENTED,
        ("V25",),
    ),
    Rule(
        "S29",
        "LOOP",
        "A LOOP over a missing, null or empty array runs its children zero times and succeeds.",
        ASSUMED,
        ("V26",),
    ),
)

RULES_BY_ID: dict[str, Rule] = {item.id: item for item in RULES}

# Platform services that clear or change the whole pipeline (S26, S27): name -> effect.
PIPELINE_RESET: dict[str, str] = {
    "pub.flow:clearPipeline": "clears",
    "pub.flow:restorePipeline": "changes",
    "pub.flow:restorePipelineFromFile": "changes",
}


def rule(rule_id: str) -> Rule:
    """The rule with this id; an unknown id is a programming error."""
    return RULES_BY_ID[rule_id]


def assumption_label(rule_ids: Iterable[str]) -> str | None:
    """`assumption S4, S7` for the assumed rules among `rule_ids`, else None."""
    assumed = sorted(
        {rule_id for rule_id in rule_ids if rule(rule_id).assumed},
        key=lambda rule_id: int(rule_id[1:]),
    )
    return f"assumption {', '.join(assumed)}" if assumed else None
