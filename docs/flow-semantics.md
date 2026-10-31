# FLOW semantics used by the conditional-flow analysis

wm-doc never runs a service. When it says which steps run under which conditions, or where a
value that a BRANCH tests comes from, it relies on Integration Server FLOW behaviour. Every such
rule is listed in `src/wm_doc/flow_semantics.py` with an id (S1-S38) and a status:

| Status | Meaning | How readers see it |
| --- | --- | --- |
| documented | Described in the IBM webMethods 10.15 documentation | The rule id only |
| assumed | Not confirmed for IS 10.15: the documentation is silent or contradicts itself | "assumption S#" next to the conclusion |
| verified | Confirmed on IS 10.15 with the checks below | The rule id only |

The statuses come from the owner's audit of the IBM 10.15 documentation (2026-10-27). Nothing
was run on a server for that audit, so no rule is verified yet. Pages never write a status by
hand: every citation is produced from the registry (`rule_label`, `assumption_label`), so a
status change in `flow_semantics.py` reaches every page, and a test fails if a page names an
assumption for a rule that is not assumed.

After a check, change the rule in `flow_semantics.py` and its row below; a test keeps the two in
step (the statements here are short summaries of the ones in the code). Rule ids are never
renumbered: when the audit split a rule, the original id kept one part and the other parts got
new ids (S31-S38).

## Rules

| Id | Topic | Rule | Status | Checks | Sources |
| --- | --- | --- | --- | --- | --- |
| S1 | BRANCH | One evaluation of a BRANCH runs at most one of its children. | documented | | [1], [2] |
| S2 | BRANCH | With a switch, a label matches the switch value as an exact, case-sensitive string; Designer requires distinct labels. | documented | | [1] |
| S3 | BRANCH | With a switch, `$null` matches a missing or null switch variable. | documented | V2 | [1] |
| S4 | BRANCH | With a switch, a blank label matches an existing empty string, not a missing or null value. | documented | V3 | [1] |
| S5 | BRANCH | With a switch, a label between slashes (`/.../`) is a regular expression. | documented | V4 | [1] |
| S6 | BRANCH | `$default` runs only when no other child matched, wherever it is placed. | documented | V5 | [1] |
| S7 | BRANCH | An existing switch value that matches no child (or no true label expression), without `$default`: the BRANCH does nothing. | documented | V6 | [1], [2] |
| S8 | BRANCH | Label expressions: evaluated in document order, first true wins, `$default` when none is true; `$null` and blank labels are ignored; a switch together with label expressions is invalid. | documented | V7 | [1], [2], [8] |
| S9 | BRANCH | A String or constrained Object switch; an object is compared by its string form. | documented | V8 | [1], [2] |
| S10 | SEQUENCE | EXIT-ON FAILURE stops at the first failure; SUCCESS stops at the first success (a successful MAP does not always stop it); DONE runs every child. | documented | V9 | [2], [3] |
| S11 | EXIT | EXIT leaves `$parent`, the innermost LOOP or REPEAT (`$loop`), only the current iteration (`$iteration`, no FAILURE), `$flow` or the nearest enclosing step with the label; naming a step that does not enclose it fails. | documented | V11, V29 | [1], [2], [4] |
| S12 | EXIT | `$loop` ends the whole LOOP or REPEAT, `$iteration` only the current iteration; the OUT-ARRAY for an iteration left early is not documented. | documented | V29 | [1], [4] |
| S13 | TRY/CATCH | A failure in TRY runs the first CATCH that handles it, then FINALLY; FINALLY also runs after TRY or CATCH finishes. | documented | V12 | [4] |
| S14 | TRY/CATCH | Since 10.3 TRY, CATCH and FINALLY are sibling steps under one parent, with no enclosing EXIT-ON SUCCESS sequence; the exact 10.15 flow.xml is not confirmed. | assumed | V13, V25 | [4] |
| S15 | Pipeline | TRY does not roll back the pipeline by default (configurable): CATCH sees what TRY changed. | documented | V14 | [3], [4] |
| S16 | INVOKE | An invoked service shares the caller's pipeline; whatever it leaves there is visible after the call. | documented | V24 | [5], [9] |
| S17 | INVOKE | Values written by an INVOKE input map stay after the call unless dropped. | assumed | V15 | [5] |
| S18 | Transformer | A transformer sees only its input map; only linked outputs reach the pipeline; without linked outputs it does not run; transformers of one MAP have no guaranteed order. | documented | V32 | [5] |
| S19 | MAP | The order of the links, sets and drops of one MAP is not documented; wm-doc assumes all sources are read first, drops last. | assumed | V16 | [5] |
| S20 | MAP | A link whose source is absent leaves the target unchanged. | assumed | V17 | [5] |
| S21 | MAP | Overwrite off only sets a missing value; variable substitution replaces `%name%` references (global variables with global substitution). | documented | V18 | [5] |
| S22 | LOOP | Inside a LOOP the IN-ARRAY path names the current element; OUT-ARRAY collects one value per iteration; element changes are not always written back. | documented | V19 | [1], [2] |
| S23 | REPEAT | REPEAT runs once, then repeats on SUCCESS or FAILURE: COUNT=N allows at most N+1 attempts (0: one, -1 or blank: no limit); the interval's XML name is not confirmed. | documented | V20 | [1], [2] |
| S24 | Scope | A step with a scope works on one document, as a view of it, not a copy. | documented | V21 | [2], [3] |
| S25 | MAP | A conditional link applies only when its condition is true; several true links to one target give an undetermined result. | documented | V22, V33 | [5] |
| S26 | Pipeline | `pub.flow:clearPipeline` removes every field except the preserved ones. | documented | | [6] |
| S27 | Pipeline | `pub.flow:restorePipeline*`: `$merge` false (default) replaces the pipeline, true merges with the saved values winning; not yet confirmed for 10.15. | assumed | V23 | [6], [7] |
| S28 | BRANCH | A direct child of a BRANCH is a case labelled by its NAME; MAP, INVOKE, EXIT, LOOP, REPEAT and SEQUENCE can be, TRY, CATCH and FINALLY cannot. | documented | V25 | [4] |
| S29 | LOOP | An existing empty array runs zero times; a missing IN-ARRAY or a value that is not an array fails the LOOP; an explicit null is not documented and not relied on. | documented | V26 | [2] |
| S30 | EXIT | An EXIT `$parent` that is itself a BRANCH child leaves the BRANCH. | documented | V10 | [1], [2] |
| S31 | BRANCH | With a switch, a missing switch variable fails the BRANCH when there is no `$null` and no `$default` child. | documented | V6, V34 | [1], [2] |
| S32 | SEQUENCE | When every child of an EXIT-ON SUCCESS sequence fails, the sequence fails; the documentation contradicts itself here. | assumed | V9 | [2], [3] |
| S33 | TRY/CATCH | EXIT `$flow` with FAILURE skips every CATCH and FINALLY of the service. | documented | V12, V30 | [4] |
| S34 | TRY/CATCH | An EXIT with SUCCESS that leaves TRY or CATCH runs FINALLY first. | documented | V12 | [4] |
| S35 | TRY/CATCH | A CATCH handles only the failures its filter selects; an unhandled failure, or a new one in CATCH or FINALLY, fails the step after FINALLY. | documented | V31 | [4] |
| S36 | Pipeline | After a failed child of an EXIT-ON SUCCESS or DONE sequence, or a failed attempt of a REPEAT on FAILURE, the first pipeline level is rolled back; nested documents changed in place may keep their changes. | documented | V14, V28 | [3], [4], [5] |
| S37 | BRANCH | When labels can match the same value (a repeated label, or overlapping patterns), the first matching child in document order is assumed to win. | assumed | V1 | [1] |
| S38 | MAP | Linking a whole document copies a reference: a change inside it through one field is seen through the other; a String is copied by value. | documented | V27 | [5] |

### Sources

The IBM webMethods documentation the audit used (10.15 unless noted):

1. [Building flow services][1] (Integration Server)
2. [webMethods flow steps][2] (Designer)
3. [Building flow services][3] (Designer; SEQUENCE rollback)
4. [Failure handling with TRY, CATCH and FINALLY steps][4]
5. [Mapping data in flow services][5]
6. [WmPublic flow folder][6]
7. [pub.flow:restorePipeline][7] (11.1, cross-check only)
8. [Integration Server messages][8]
9. [Building services][9]

[1]: https://www.ibm.com/docs/en/webmethods-integration/wm-integration-server/10.15.0?topic=guide-building-flow-services
[2]: https://www.ibm.com/docs/en/webmethods-integration/wm-designer/10.15.0?topic=help-webmethods-flow-steps
[3]: https://www.ibm.com/docs/en/webmethods-integration/wm-designer/10.15.0?topic=help-building-flow-services
[4]: https://www.ibm.com/docs/en/webmethods-integration/wm-integration-server/10.15.0?topic=sdg-failure-handling-in-flow-services-using-try-catch-finally-steps
[5]: https://www.ibm.com/docs/en/webmethods-integration/wm-integration-server/10.15.0?topic=guide-mapping-data-in-flow-services
[6]: https://www.ibm.com/docs/en/webmethods-integration/wm-integration-server/10.15.0?topic=guide-flow-folder
[7]: https://www.ibm.com/docs/en/webmethods-integration/wm-integration-server/11.1.0?topic=folder-pubflowrestorepipeline
[8]: https://www.ibm.com/docs/en/webmethods-integration/wm-integration-server/10.15.0?topic=reference-integration-server-messages
[9]: https://www.ibm.com/docs/en/webmethods-integration/wm-integration-server/10.15.0?topic=guide-building-services

### What the audit changed in the analysis

- No case matched (S7, S31): a switch value that exists falls through, but a missing one fails
  the BRANCH when there is neither `$null` nor `$default`. Statically the two cannot be told
  apart, so a page never shows the fall-through as the only outcome.
- LOOP (S29): a missing IN-ARRAY fails the LOOP; zero iterations happen only for an existing
  empty array. The failure states before the LOOP reach any CATCH or later alternative.
- TRY, CATCH and FINALLY (S13, S33-S35) are read as one step, in both the sibling form and the
  older EXIT-ON SUCCESS form. A CATCH runs only when something in the TRY may fail (any step but
  an EXIT may); FINALLY runs unless every way out is EXIT `$flow` with FAILURE, which skips
  every CATCH and FINALLY. A CATCH with settings wm-doc does not read may filter failures, so a
  failure EXIT handled by it may also go further.
- Rollback (S15, S36): a failed child of an EXIT-ON SUCCESS or DONE sequence and a failed
  attempt of a REPEAT on FAILURE roll back first-level fields; nested fields keep both values
  as possible. TRY does not roll back for its CATCH.
- EXIT `$iteration` (S11, S12) ends only the current iteration; the next one starts from the
  state it left.
- Linked documents (S38): a line that changes a field inside one of two linked documents may
  also change the same field of the other; that change is listed as possible, so neither field
  "comes from" its own definition alone.
- In an EXIT-ON DONE sequence a step that fails before its EXIT does not stop the later steps,
  so they no longer claim that the EXIT's case was not taken; an EXIT-ON SUCCESS sequence with
  no step at all finishes.
- A transformer without linked outputs never runs (S18); `$null` and blank labels never run in
  label-expression mode (S8); a later EXIT-ON SUCCESS alternative may also run after a MAP that
  succeeded (S10).

### Rule status and the facts hash

The `### Decisions` part of a description file's facts block is refreshed on every run but is
not part of its facts hash, so a status change never marks a description stale. Stage 4 will
hash the conditional logic: that hashed form must carry only behaviour (which calls run under
which conditions, which origins reach a decision), never a rule's status or an "assumption"
label, so that changing a rule from assumed to verified never makes approved descriptions
stale. Only a change of what the analysis concludes may.

## Owner checklist (IS 10.15, Designer)

Create a throwaway package (for example `DocGenChecks`; wm-doc skips packages named `Wm*`) with
one FLOW service per check. Each service needs only MAP steps, EXIT steps or harmless platform
services; none touches a real system. Run each with the inputs given and note the result
pipeline (or the error). For V13, V20, V21, V22, V25 and V31, share the service's `flow.xml`:
it contains only these test steps, no production code. Save every service with Designer; do not
edit `flow.xml` by hand.

| Check | Build | Run with | Question |
| --- | --- | --- | --- |
| V1 | BRANCH on `/x` with two different patterns that overlap: `/^A/` sets `/out=first`, then `/A.*/` sets `/out=second`. Also try to give two children the same label `A` | `x=ABC` | Is `/out` "first"? Does Designer refuse the repeated label? |
| V2 | BRANCH on `/x`: `$null` sets `/out=null`, `$default` sets `/out=default` | `x` absent; `x=""`; `x` present with a null value | Which child runs in each case? |
| V3 | BRANCH on `/x`: a child with a blank label sets `/out=blank`, `$default` sets `/out=default` | `x=""`; `x` absent | Which child runs in each case? Does Designer allow the blank label? |
| V4 | BRANCH on `/x`: `/^AC/` sets `/out=regex`, `$default` sets `/out=default` | `x=ACTIVE`; `x=xAC`; `x=active` | Regex matched? Anchored as written? Case-sensitive? |
| V5 | BRANCH on `/x` with `$default` first (`/out=default`), then A (`/out=a`). Separately, a BRANCH with label expressions and no switch: `$default` first, then `%x% == "A"` | `x=A` | Is `/out` "a" in both? |
| V6 | BRANCH on `/x` with only child A, then a MAP after the BRANCH setting `/after=reached` | `x=B`; `x` absent | Does `x=B` succeed with `/after=reached`? Does `x` absent fail (see V34)? |
| V7 | BRANCH with label expressions and no switch; children `%y% == "1"` (`/out=y1`), a blank label (`/out=blank`), `$null` (`/out=null`), `$default` (`/out=default`). Repeat without `$default`, with a MAP after the BRANCH. Also try to set a switch as well | `y=1`; `y=2`; `y` absent | Are the blank and `$null` children never run? Without `$default`, does `y=2` reach the MAP? Does Designer refuse a switch with label expressions? |
| V8 | Set `/x` to an Integer (for example `pub.math:toNumber` with `convertAs=java.lang.Integer`), as a constrained Object; BRANCH on `/x` with child `5` | number 5 | Does child `5` match? |
| V9 | SEQUENCE EXIT-ON SUCCESS: (a) both children fail (EXIT `$parent` FAILURE); (b) the first fails, the second sets `/second=ran`; (c) the first child is a MAP that succeeds, the second sets `/second=ran`; (d) as (c) with a transformer in the MAP. A MAP after the sequence sets `/after=reached` | none | In each case: does the sequence fail, is `/second` set, is `/after` set? (Highest priority: the documentation contradicts itself.) |
| V10 | BRANCH on `/x` whose child A is an EXIT `$parent` SUCCESS (the child itself, not inside a SEQUENCE); after the BRANCH, set `/after=reached`. Repeat with SIGNAL FAILURE | `x=A` | Is `/after=reached` with SUCCESS? Does FAILURE fail the service? |
| V11 | SEQUENCE "S" containing SEQUENCE "S" containing EXIT FROM "S"; after the inner one set `/inner=after`, after the outer one set `/outer=after` | none | Which "S" was left? |
| V12 | TRY/CATCH/FINALLY where CATCH sets `/catch=ran` and FINALLY sets `/finally=ran`: (a) TRY with EXIT `$flow` SUCCESS; (b) TRY with EXIT `$parent` FAILURE; (c) TRY with EXIT `$flow` FAILURE; (d) TRY invoking a service that throws, with a CATCH without filter and then with a matching filter | none | Which blocks ran in each case? |
| V13 | A TRY/CATCH/FINALLY service with at least two CATCH blocks and a nested TRY | - | Share its `flow.xml`. |
| V14 | (a) TRY: MAP sets `/x=set` and `/doc/f=set`, then a failing step; CATCH reads both; repeat with the TRY rollback option on if the server offers one. (b) SEQUENCE EXIT-ON SUCCESS: the first child sets both then fails, the second child reads them. (c) as (b) with EXIT-ON DONE. (d) REPEAT on FAILURE, COUNT 1: the attempt sets both then fails; the retry reads them | `doc` present before the step | Which values does each reader see? |
| V15 | INVOKE `pub.string:toUpper` with an input map setting its `inString` to `abc`; repeat invoking your own service that drops `inString`, and one that sets it to `changed` | none | After each INVOKE, is `/inString` in the pipeline, and with which value? |
| V16 | One MAP with links `/a` to `/b` and `/b` to `/c`; a second MAP with a link `/s` to `/t` that also drops `/s` (Designer does not allow a set and a link on the same target) | `a=new`, `b=old`, `s=copied` | Is `/c` "old" or "new"? Is `/t` "copied" and `/s` gone? |
| V17 | MAP sets `/t=old`; the next MAP links `/missing` to `/t`. Repeat with a source present but null, and with a source inside a document (`/doc/missing`) | none | Is `/t` still "old" in each case? |
| V18 | Set with overwrite off on `/t` when `/t` is absent, empty, null; set with variable substitution `%x%-suffix` using pipeline substitution only, global only, and both, with `x` present and absent | `x=val` | Which cases set `/t`? What is the result of each substitution, or the error? |
| V19 | LOOP over `/items` (two documents) setting `/items/status=done`; repeat with OUT-ARRAY `/results`; then with an EXIT `$loop` and an EXIT `$iteration` on the second item | two items | Are the items changed after the loop? What does `/results` hold in each case? |
| V20 | REPEAT on FAILURE around a failing step with COUNT 0, then 2; COUNT -1 stopped by a counter and an EXIT; REPEAT on SUCCESS with COUNT 2 around a step that succeeds. Set a repeat interval | none | How many attempts in each case? Share the `flow.xml` to see how the interval is written. |
| V21 | A step with a scope set to `/doc`, changing a field; a second document `/other` alongside | `doc`, `other` present | Share the `flow.xml`. Is `/doc` changed in place (a view, not a copy)? |
| V22 | A map link with a condition | condition true; false | Share the `flow.xml`. Is the link applied only when true? |
| V23 | `pub.flow:savePipeline` with `$name=check` and `/a=1`; MAP sets `/a=2` and `/b=new`; `pub.flow:restorePipeline` with `$name=check`, first with `$merge=false`, then with `$merge=true` | none | After each restore: is `/a` 1, and is `/b` still there? |
| V24 | Service B sets `/extra=leaked`: once without an output signature, once with one that does not list `extra`; service A invokes B, once as an INVOKE and once as a transformer | none | After the call in A, is `/extra` in the pipeline in each case? |
| V25 | One service with a REPEAT, a LOOP with an EXIT `$loop`, a BRANCH with label expressions, a BRANCH whose children are a MAP and an INVOKE labelled directly (not wrapped in SEQUENCEs), and a TRY/CATCH inside a SEQUENCE under a BRANCH (TRY cannot be a direct BRANCH child) | - | Share its `flow.xml`. |
| V26 | LOOP over `/items`, setting `/ran=yes` inside and `/after=reached` after | `items` absent; present but null; an empty list; a string | Which runs fail? Which reach `/after` without `/ran`? |
| V27 | MAP: link document `/a` to `/b`; the next MAP sets `/a/f=changed`; read `/b/f`. Repeat with String fields `/s` to `/t`, then change `/s` | `a/f=old`, `s=old` | Is `/b/f` "changed" (the document was linked by reference)? Is `/t` still "old"? |
| V28 | SEQUENCE EXIT-ON SUCCESS, SEQUENCE EXIT-ON DONE and REPEAT on FAILURE: each sets `/top=x` and `/doc/field=x` before a failure | `doc` present | After each failure, are `/top` and `/doc/field` back to their earlier values? |
| V29 | LOOP over two items and a REPEAT, each with an EXIT `$iteration` on the first iteration and an OUT-ARRAY; try also EXIT `$iteration` with FAILURE | two items | Does the next iteration run? What does the OUT-ARRAY hold for the skipped one? Does Designer refuse FAILURE? |
| V30 | TRY with EXIT `$flow` FAILURE, CATCH and FINALLY setting fields; service A invokes it inside its own TRY/CATCH | none | Does no CATCH or FINALLY of the service run? Does A's CATCH see the failure? |
| V31 | Two CATCH blocks with different failure classes and INCLUDE/EXCLUDE selection, with a disabled step between them; a TRY that throws each class | each class | Which CATCH handles each failure? Share the `flow.xml` to see how the filters are written. |
| V32 | (a) A transformer (for example `pub.flow:debugLog`) whose outputs are not linked; (b) two transformers in one MAP that both write `/t` through their outputs | none | Does (a) run (look in the server log)? Which value does `/t` get in (b), and is it the same every run? |
| V33 | Two conditional links to one target `/t`, both conditions true, from `/a` and `/b` | `a=1`, `b=2` | Which value does `/t` get, and is it the same every run? |
| V34 | BRANCH on `/x` with only child A (no `$null`, no `$default`), then a MAP setting `/after=reached` | `x` absent; `x=B` | Does `x` absent fail the service? Does `x=B` reach `/after`? |

Report results by check id. Each result changes one or more rules from assumed to verified, or
corrects a rule statement; a corrected rule may also need the analysis to change.
