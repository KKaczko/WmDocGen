# FLOW semantics used by the conditional-flow analysis

wm-doc never runs a service. When it says which steps run under which conditions, or where a
value that a BRANCH tests comes from, it relies on Integration Server FLOW behaviour. Every such
rule is listed in `src/wm_doc/flow_semantics.py` with an id (S1-S26) and a status:

| Status | Meaning | How readers see it |
| --- | --- | --- |
| documented | Described in the webMethods FLOW documentation | No label |
| assumed | Plausible, not yet confirmed on IS 10.15 | "assumption S#" next to the conclusion |
| verified | Confirmed on IS 10.15 with the checks below | No label |

After a check, change the rule in `flow_semantics.py` and its row below; a test keeps the two in
step (the statements here are short summaries of the ones in the code).

## Rules

| Id | Topic | Rule | Status | Checks |
| --- | --- | --- | --- | --- |
| S1 | BRANCH | One evaluation of a BRANCH runs at most one of its children. | documented | |
| S2 | BRANCH | With a switch, a child runs when its label equals the switch value as an exact, case-sensitive string; the first matching child in document order wins. | documented | V1 |
| S3 | BRANCH | `$null` matches when the switch variable is missing or null. | documented | V2 |
| S4 | BRANCH | A blank label matches an empty-string switch value. | assumed | V3 |
| S5 | BRANCH | A label between slashes (`/.../`) is a regular expression. | assumed | V4 |
| S6 | BRANCH | `$default` runs only when no other child matched, wherever it is placed. | assumed | V5 |
| S7 | BRANCH | No match and no `$default`: the BRANCH does nothing and succeeds. | assumed | V6 |
| S8 | BRANCH | Label expressions are evaluated in document order; the first true one wins. | documented | V7 |
| S9 | BRANCH | A non-string switch value is compared by its string form. | assumed | V8 |
| S10 | SEQUENCE | EXIT-ON FAILURE stops at the first failure and fails; SUCCESS stops at the first success; DONE runs every child. | documented | V9 |
| S11 | EXIT | EXIT leaves `$parent`, the innermost LOOP or REPEAT (`$loop`), `$flow` or the nearest enclosing step with the label, with SUCCESS or FAILURE. | documented | V10, V11 |
| S12 | EXIT | Exiting a LOOP ends the whole loop, not only the current iteration. | documented | |
| S13 | TRY/CATCH | A failure or EXIT FAILURE inside TRY runs CATCH; FINALLY always runs, also after an EXIT. | assumed | V12 |
| S14 | TRY/CATCH | IS 10.15 writes TRY/CATCH (and FINALLY) as sibling FORM sequences inside an EXIT-ON SUCCESS sequence; older services use an EXIT-ON SUCCESS sequence without FORM. | assumed | V13, V25 |
| S15 | Pipeline | Changes a step made before it failed stay in the pipeline when a CATCH, an EXIT-ON SUCCESS sequence or a REPEAT continues. | assumed | V14 |
| S16 | INVOKE | An invoked service works on the caller's pipeline; whatever it leaves there is visible after the call. | documented | V24 |
| S17 | INVOKE | Values written by an INVOKE input map stay in the pipeline after the call unless dropped. | assumed | V15 |
| S18 | Transformer | A transformer only sees its input map; only outputs its output map copies reach the pipeline. | documented | |
| S19 | MAP | Order of copies, sets and drops in one MAP step: assumed to read every source before writing, drops last. | assumed | V16 |
| S20 | MAP | A copy whose source is absent leaves the target unchanged. | assumed | V17 |
| S21 | MAP | Overwrite off only sets a missing value; variable substitution replaces `%name%` references (global variables with global substitution). | documented | V18 |
| S22 | LOOP | Inside a LOOP, the IN-ARRAY path names the current element; OUT-ARRAY collects one value per iteration. | documented | V19 |
| S23 | REPEAT | REPEAT runs its children again up to COUNT more times (-1 without limit), waiting BACK-OFF seconds. | assumed | V20 |
| S24 | Scope | A step with a scope works on one document instead of the whole pipeline. | assumed | V21 |
| S25 | MAP | A copy can carry a condition that decides at run time whether it is applied. | assumed | V22 |
| S26 | Pipeline | `pub.flow:clearPipeline` removes every field except the preserved ones. | documented | |
| S27 | Pipeline | `pub.flow:restorePipeline*` put saved values back; replace or merge is not confirmed. | assumed | V23 |
| S28 | BRANCH | Any step can be a child of a BRANCH; its NAME is the case label. | documented | V25 |
| S29 | LOOP | A LOOP over a missing, null or empty array runs zero times and succeeds. | assumed | V26 |

## Owner checklist (IS 10.15, Designer)

Create a throwaway package (for example `DocGenChecks`; wm-doc skips packages named `Wm*`) with
one FLOW service per check. Each
service needs only MAP steps, EXIT steps or harmless platform services; none touches a real
system. Run each with the inputs given and note the result pipeline. For V13, V21, V22 and V25,
share the service's `flow.xml`: it contains only these test steps, no production code.

| Check | Build | Run with | Question |
| --- | --- | --- | --- |
| V1 | BRANCH on `/x`: child A sets `/out=first`, a second child also labelled A sets `/out=second` | `x=A` | Is `/out` "first"? |
| V2 | BRANCH on `/x`: `$null` sets `/out=null`, `$default` sets `/out=default` | `x` absent; `x=""` | Absent gives null? Empty string gives which? |
| V3 | BRANCH on `/x`: a child with a blank label sets `/out=blank`, `$default` sets `/out=default` | `x=""`; `x` absent | Which child runs in each case? Does Designer allow the blank label? |
| V4 | BRANCH on `/x`: `/^AC/` sets `/out=regex`, `$default` sets `/out=default` | `x=ACTIVE`; `x=xAC`; `x=active` | Regex matched? Anchored as written? Case-sensitive? |
| V5 | BRANCH on `/x` with `$default` first (`/out=default`), then A (`/out=a`); repeat with label expressions (`%x% == "A"`) | `x=A` | Is `/out` "a" in both modes? |
| V6 | BRANCH on `/x` with only child A, then a MAP after the BRANCH setting `/after=reached` | `x=B` | Does the service succeed with `/after=reached`? |
| V7 | BRANCH with label expressions and also a switch `/x`; children `%y% == "1"` (`/out=y1`), an unlabelled child (`/out=unlabelled`), `$null` (`/out=null`), `$default` | `y=1`; `y=2`; `y` absent | Is the switch ignored? Which child runs for each input? |
| V8 | Set `/x` to an Integer (for example `pub.math:toNumber` with `convertAs=java.lang.Integer`); BRANCH on `/x` with child `5` | number 5 | Does child `5` match? |
| V9 | SEQUENCE EXIT-ON SUCCESS whose two children both fail (EXIT `$parent` FAILURE) | none | Does the sequence, and so the service, fail? |
| V10 | BRANCH on `/x` whose child A is an EXIT `$parent` SUCCESS (the child itself, not inside a SEQUENCE); after the BRANCH, set `/after=reached` | `x=A` | Is `/after=reached`, so the EXIT left only the BRANCH? |
| V11 | SEQUENCE "S" containing SEQUENCE "S" containing EXIT FROM "S"; after the inner one set `/inner=after`, after the outer one set `/outer=after` | none | Which "S" was left? |
| V12 | TRY/CATCH/FINALLY: (a) TRY with EXIT `$flow` SUCCESS; (b) TRY with EXIT `$parent` FAILURE; CATCH sets `/catch=ran`, FINALLY sets `/finally=ran` | none | Which blocks ran in (a) and (b)? |
| V13 | Any TRY/CATCH/FINALLY service | - | Share its `flow.xml`. |
| V14 | (a) TRY: MAP sets `/x=set`, then a failing step; CATCH reads `/x`. (b) SEQUENCE EXIT-ON SUCCESS: first child sets `/x=set` then fails, second child sets `/y=ran` | none | Is `/x` still "set" in CATCH and after the sequence? |
| V15 | INVOKE `pub.string:toUpper` with an input map setting its `inString` to `abc` | none | After the INVOKE, is `/inString` in the pipeline? |
| V16 | One MAP: set `/t=set` and copy `/s` to `/t`; also copy `/a` to `/b` and `/b` to `/c` | `s=copied`, `a=new`, `b=old` | Value of `/t`? Is `/c` "old" or "new"? |
| V17 | MAP sets `/t=old`; the next MAP copies `/missing` to `/t` | none | Is `/t` still "old"? |
| V18 | Set with overwrite off on `/t` when `/t` is absent, empty, null; set with variable substitution `%x%-suffix` | `x=val` | Which cases set `/t`? Result of the substitution? |
| V19 | LOOP over `/items` (two documents) setting `/items/status=done`; repeat with OUT-ARRAY `/results` | two items | Are the items changed after the loop? What does `/results` hold? |
| V20 | REPEAT on failure around a failing step with COUNT 0, then -1 (stop with a counter) | none | How many attempts in each case? |
| V21 | Any step with a scope set in its properties | - | Share its `flow.xml`. |
| V22 | A map link with a condition | - | Share its `flow.xml`. |
| V23 | `pub.flow:savePipeline` with `/a=1`, then MAP sets `/a=2` and `/b=new`, then `pub.flow:restorePipeline` | none | After the restore: is `/a` 1, and is `/b` still there? |
| V24 | Service B sets `/extra=leaked` but declares no outputs; service A invokes B | none | After the INVOKE in A, is `/extra` in the pipeline? |
| V25 | One service with a REPEAT, a LOOP with an EXIT `$loop`, a BRANCH with label expressions, and a BRANCH whose children are a MAP and an INVOKE labelled directly (not wrapped in SEQUENCEs) | - | Share its `flow.xml`. |
| V26 | LOOP over `/items`, setting `/ran=yes` inside and `/after=reached` after | `items` absent; empty list | Does the service succeed with `/after=reached` and no `/ran`? |

Report results by check id. Each result changes one or more rules from assumed to verified, or
corrects a rule statement.
