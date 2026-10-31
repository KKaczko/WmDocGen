"""Integration Server FLOW behaviour that the conditional-flow analysis relies on.

Static analysis cannot run a service, so every conclusion about which step runs when rests on
Integration Server behaviour. Each rule here has an id that derived facts cite and a status:

- DOCUMENTED: described in the IBM webMethods 10.15 documentation; relied on without a label.
- ASSUMED: plausible but not confirmed for IS 10.15 (missing or contradictory documentation);
  conclusions that rest on it are shown to readers as assumptions.
- VERIFIED: confirmed by the repository owner on IS 10.15 with the test services described in
  `docs/flow-semantics.md`.

Readers see a rule's status only through `assumption_label` and `rule_label`, never through
fixed text, so a status change here updates every page. After a check, change the rule here and
its row in `docs/flow-semantics.md`; a test keeps the two in step. Rule ids are never
renumbered: a rule that splits keeps its id for one part and the other parts get new ids.
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
        "case-sensitive string. Designer requires the labels of one BRANCH to be distinct.",
        DOCUMENTED,
    ),
    Rule(
        "S3",
        "BRANCH",
        "With a switch, the label $null matches when the switch variable is missing or null.",
        DOCUMENTED,
        ("V2",),
    ),
    Rule(
        "S4",
        "BRANCH",
        "With a switch, a blank label matches a switch value that exists and is an empty "
        "string; a missing or null value does not match it.",
        DOCUMENTED,
        ("V3",),
    ),
    Rule(
        "S5",
        "BRANCH",
        "With a switch, a label written between slashes (/.../) is a regular expression matched "
        "against the switch value.",
        DOCUMENTED,
        ("V4",),
    ),
    Rule(
        "S6",
        "BRANCH",
        "The $default child runs only when no other child matched; it is treated as the last "
        "child wherever it is placed.",
        DOCUMENTED,
        ("V5",),
    ),
    Rule(
        "S7",
        "BRANCH",
        "When the switch value exists but matches no child, or no label expression is true, and "
        "there is no $default child, the BRANCH does nothing and the next step runs.",
        DOCUMENTED,
        ("V6",),
    ),
    Rule(
        "S8",
        "BRANCH",
        "With label expressions, the labels are evaluated in document order and the first true "
        "one wins; $default runs when none is true, and $null and blank labels are ignored. A "
        "switch together with label expressions is an invalid configuration.",
        DOCUMENTED,
        ("V7",),
    ),
    Rule(
        "S9",
        "BRANCH",
        "A switch can be a String or a constrained Object; an object value (for example an "
        "Integer) is compared by its string form.",
        DOCUMENTED,
        ("V8",),
    ),
    Rule(
        "S10",
        "SEQUENCE",
        "EXIT-ON FAILURE stops at the first child that fails and fails; EXIT-ON SUCCESS stops "
        "at the first child that succeeds, although a MAP step that succeeds does not always "
        "stop it; EXIT-ON DONE runs every child and ignores their failures.",
        DOCUMENTED,
        ("V9",),
    ),
    Rule(
        "S11",
        "EXIT",
        "EXIT leaves the parent step ($parent, whatever its type), the innermost LOOP or REPEAT "
        "($loop), only the current iteration of the innermost LOOP or REPEAT ($iteration, which "
        "does not allow FAILURE), the whole service ($flow) or the nearest enclosing step with "
        "the given label, with SUCCESS or FAILURE. Naming a step that does not enclose the EXIT "
        "fails at run time.",
        DOCUMENTED,
        ("V11", "V29"),
    ),
    Rule(
        "S12",
        "EXIT",
        "EXIT $loop ends the whole LOOP or REPEAT; EXIT $iteration ends only the current "
        "iteration and the next one runs. What the OUT-ARRAY holds for an iteration that was "
        "left early is not documented.",
        DOCUMENTED,
        ("V29",),
    ),
    Rule(
        "S13",
        "TRY/CATCH",
        "A failure inside TRY runs the first CATCH that handles it and then FINALLY; FINALLY "
        "also runs after TRY or CATCH finishes normally.",
        DOCUMENTED,
        ("V12",),
    ),
    Rule(
        "S14",
        "TRY/CATCH",
        "Since IS 10.3, TRY, CATCH and FINALLY are separate sibling steps under one parent "
        "(zero or more CATCH, at most one FINALLY) and need no enclosing EXIT-ON SUCCESS "
        "sequence. wm-doc reads them as SEQUENCE steps with a FORM attribute under any parent, "
        "and reads the older pattern, an EXIT-ON SUCCESS sequence without FORM, as "
        "alternatives. The exact flow.xml that IS 10.15 writes is not confirmed.",
        ASSUMED,
        ("V13", "V25"),
    ),
    Rule(
        "S15",
        "Pipeline",
        "TRY does not roll back the pipeline by default (a server setting can change this): a "
        "CATCH sees the changes TRY made before it failed.",
        DOCUMENTED,
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
        "unless they are dropped; the called service may still drop or replace them.",
        ASSUMED,
        ("V15",),
    ),
    Rule(
        "S18",
        "Transformer",
        "A transformer only sees what its input map gives it, and only the outputs its output "
        "map links reach the pipeline. A transformer with no linked outputs does not run, and "
        "the transformers of one MAP run in no guaranteed order.",
        DOCUMENTED,
        ("V32",),
    ),
    Rule(
        "S19",
        "MAP",
        "The order in which one MAP step applies its links, sets and drops is not documented; "
        "wm-doc assumes every source is read before any target is written, with drops last. "
        "Designer does not allow a set and a link on the same target.",
        ASSUMED,
        ("V16",),
    ),
    Rule(
        "S20",
        "MAP",
        "A link whose source is absent leaves the target unchanged.",
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
        "one value per iteration. Changes to the element are not always written back to the "
        "original list.",
        DOCUMENTED,
        ("V19",),
    ),
    Rule(
        "S23",
        "REPEAT",
        "REPEAT always runs its children once; with COUNT=N it makes at most N+1 attempts (0 "
        "means one attempt, -1 or blank means no limit), repeating on SUCCESS or on FAILURE as "
        "configured and waiting the repeat interval in between (the interval's flow.xml "
        "attribute name is not confirmed).",
        DOCUMENTED,
        ("V20",),
    ),
    Rule(
        "S24",
        "Scope",
        "A step with a scope works on one document of the pipeline; the scope is a view of "
        "that document, not a copy.",
        DOCUMENTED,
        ("V21",),
    ),
    Rule(
        "S25",
        "MAP",
        "A link can carry a condition and is applied only when the condition is true; when "
        "several conditional links to one target are true, which one wins is not determined.",
        DOCUMENTED,
        ("V22", "V33"),
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
        "pub.flow:restorePipeline and pub.flow:restorePipelineFromFile put saved values back: "
        "with $merge false (the default) the saved pipeline replaces the current one, with "
        "$merge true the two are merged and the saved values win. Documented for later "
        "releases, not yet confirmed for 10.15.",
        ASSUMED,
        ("V23",),
    ),
    Rule(
        "S28",
        "BRANCH",
        "A step that is a direct child of a BRANCH is one of its cases, and its NAME is the "
        "case label. MAP, INVOKE, EXIT, LOOP, REPEAT and SEQUENCE steps can be direct "
        "children; TRY, CATCH and FINALLY cannot.",
        DOCUMENTED,
        ("V25",),
    ),
    Rule(
        "S29",
        "LOOP",
        "A LOOP over an existing empty array runs its children zero times; a missing IN-ARRAY, "
        "or a value that is not an array, makes the LOOP fail. What an explicit null does is "
        "not documented, and nothing here relies on it.",
        DOCUMENTED,
        ("V26",),
    ),
    Rule(
        "S30",
        "EXIT",
        "An EXIT $parent that is itself a child of a BRANCH leaves the BRANCH (the case is not "
        "a step of its own).",
        DOCUMENTED,
        ("V10",),
    ),
    Rule(
        "S31",
        "BRANCH",
        "With a switch, a switch variable that is missing makes the BRANCH fail when there is "
        "no $null and no $default child.",
        DOCUMENTED,
        ("V6", "V34"),
    ),
    Rule(
        "S32",
        "SEQUENCE",
        "When every child of an EXIT-ON SUCCESS sequence fails, the sequence fails; the IBM "
        "documentation contradicts itself on this case.",
        ASSUMED,
        ("V9",),
    ),
    Rule(
        "S33",
        "TRY/CATCH",
        "EXIT $flow with FAILURE skips every CATCH and FINALLY of the service.",
        DOCUMENTED,
        ("V12", "V30"),
    ),
    Rule(
        "S34",
        "TRY/CATCH",
        "An EXIT with SUCCESS that leaves a TRY or CATCH runs the FINALLY first.",
        DOCUMENTED,
        ("V12",),
    ),
    Rule(
        "S35",
        "TRY/CATCH",
        "A CATCH handles only the failures its filter selects. A failure that no CATCH "
        "handles, or a new failure inside CATCH or FINALLY, fails the step once FINALLY has "
        "run.",
        DOCUMENTED,
        ("V31",),
    ),
    Rule(
        "S36",
        "Pipeline",
        "After a failed child of an EXIT-ON SUCCESS or EXIT-ON DONE sequence, and after a "
        "failed attempt of a REPEAT on FAILURE, the first level of the pipeline is rolled back; "
        "documents nested in it that were changed in place may keep their changes.",
        DOCUMENTED,
        ("V14", "V28"),
    ),
    Rule(
        "S37",
        "BRANCH",
        "When the labels of one BRANCH can match the same value (a repeated label, which "
        "Designer does not allow, or overlapping patterns), the first matching child in "
        "document order is assumed to win.",
        ASSUMED,
        ("V1",),
    ),
    Rule(
        "S38",
        "MAP",
        "Linking a whole document copies a reference: both fields then name the same "
        "document, so a change made inside it through one is seen through the other. A String "
        "is copied by value.",
        DOCUMENTED,
        ("V27",),
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


def _ordered(rule_ids: Iterable[str]) -> list[str]:
    return sorted(set(rule_ids), key=lambda rule_id: int(rule_id[1:]))


def assumption_label(rule_ids: Iterable[str]) -> str | None:
    """`assumption S4, S7` for the assumed rules among `rule_ids`, else None."""
    assumed = [rule_id for rule_id in _ordered(rule_ids) if rule(rule_id).assumed]
    return f"assumption {', '.join(assumed)}" if assumed else None


def rule_label(rule_ids: Iterable[str]) -> str:
    """`S6`, `assumption S6` or `S6; assumption S19`: rules cited in prose by their status."""
    ordered = _ordered(rule_ids)
    plain = ", ".join(rule_id for rule_id in ordered if not rule(rule_id).assumed)
    assumed = assumption_label(ordered)
    return "; ".join(part for part in (plain, assumed) if part)
