# Architecture

M2a implements package/artifact inventory plus a FLOW Service static-analysis slice focused on
traceable calls, unique dependencies, and observed control-flow structure.

Subsystems:

- Discovery locates package roots, namespace folders, and artifact file combinations.
- Secure XML parsing lives in `wm_doc.xmlsafe` and rejects DTD/entity declarations.
- `Values` parsing extracts safe metadata from `manifest.v3`, `node.idf`, and `node.ndf`.
- Service analysis in `wm_doc.analysis` parses observed FLOW Service signatures and `flow.xml`
  structures without executing package code.
- Classification in `wm_doc.config` applies deterministic, case-insensitive glob rules. `neverImportant`
  rules take precedence over important service rules.
- Dependency resolution is exact-name only. It resolves static `INVOKE` and `MAPINVOKE` targets to
  discovered FLOW or Java Service metadata and keeps unresolved targets explicit in the IR.
- IR models in `wm_doc.ir` preserve source references, confidence basis, finding statuses,
  classifications, call occurrences, unique dependencies, an ordered FLOW tree, and typed findings.
- Renderers produce deterministic inventory JSON/Markdown and deterministic analysis JSON,
  per-service Markdown, and Graphviz DOT.
- The CLI exposes `wm-doc scan` and `wm-doc analyze`.

## Analysis Schema

`analysis.v1` used `edges` for concrete call sites. M2a migrates to `analysis.v2`:

- `call_occurrences` stores each concrete static `INVOKE` or `MAPINVOKE` site with source evidence,
  structural path, parent FLOW path, call type, dependency kind, and resolved status.
- `unique_dependencies` aggregates repeated calls by `(caller, target, dependency kind)` and retains
  occurrence counts plus deterministic occurrence IDs.
- `INVOKE` maps to dependency kind `INVOKES`.
- `MAPINVOKE` maps to dependency kind `USES_TRANSFORMER`.
- `flow_tree` stores ordered FLOW nodes for `FLOW`, `SEQUENCE`, `BRANCH`, derived `BRANCH_CASE`,
  `LOOP`, structural `MAP`, `INVOKE`, `MAPINVOKE`, and `EXIT`.
- `EXIT` nodes preserve observed `FROM`, `SIGNAL`, and `FAILURE-MESSAGE` attributes. Unknown EXIT
  shapes are still parsed and also produce findings.

The M2a FLOW parser is feature-based. It interprets only observed structures needed for this
milestone and records other observed uppercase FLOW elements as findings instead of treating them as
silently supported. MAP internals are deliberately deferred: `MAPCOPY`, `MAPSET`, `MAPDELETE`,
`MAPSOURCE`, `MAPTARGET`, and `DATA` currently produce partial-support findings.

Later milestones will add fuller FLOW semantics, document/spec dependency extraction, Java metadata
expansion, adapter fixtures, trigger fixtures, process graphs, and Ollama input generation. Those are
intentionally outside M2a.
