# Architecture

M2b remediation implements package/artifact inventory plus a FLOW Service static-analysis slice
focused on traceable calls, unique dependencies, observed control-flow structure, observed mapping
evidence, and policy-safe disclosure of free text.

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
  classifications, call occurrences, unique dependencies, an ordered FLOW tree, flow maps, typed
  mapping operations, transformer bindings, extraction policies, and typed findings.
- Renderers produce deterministic inventory JSON/Markdown and deterministic analysis JSON,
  per-service Markdown, and Graphviz DOT.
- The CLI exposes `wm-doc scan` and `wm-doc analyze`.

## Analysis Schema

`analysis.v1` used `edges` for concrete call sites. M2a migrated to `analysis.v2`:

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

M2b migrates to `analysis.v3`:

- `flow_maps` stores observed `MAP` containers with stable IDs, structural paths, `MODE`, parent
  call references, raw attributes, source evidence, and attached `MAPSOURCE`/`MAPTARGET` metadata
  summaries.
- `mapping_operations` stores typed `COPY`, `SET`, and `DELETE` operations derived from observed
  `MAPCOPY`, `MAPSET`, and `MAPDELETE` elements.
- `transformer_bindings` stores evidence-only bindings for `MAPINVOKE` child maps with
  `MODE="INVOKEINPUT"` or `MODE="INVOKEOUTPUT"`.
- `extraction_policy` records the active literal and free-text disclosure modes that shaped the
  output.
- Call occurrence IDs, flow map IDs, mapping operation IDs, and binding IDs use deterministic
  SHA-derived prefixes.

M2b remediation migrates to `analysis.v4`:

- Policy-controlled text is stored as structured text metadata instead of raw strings.
- Free-text policy applies before canonical serialization to service descriptions, FLOW labels,
  free-text `NAME` attributes, display labels, and mapping operation names.
- Structural and technical values remain raw when needed for static analysis, including service
  targets, pipeline paths, branch switches, loop arrays, exit attributes, and mapping endpoints.
- Raw attribute collections are filtered to technical values only. Free-text attributes are stored
  as policy-safe text metadata, and unknown attributes preserve name/source/presence without raw
  values unless explicitly classified as technical.
- The extraction policy snapshot records the active modes and the deterministic secret guard
  strategy.
- Mapping operations keep service-local discovery order and additionally expose per-map direct-child
  order plus document traversal order. These are evidence orderings, not runtime execution order.

The M2b FLOW parser remains feature-based. It interprets only observed structures needed for this
milestone and records other observed uppercase FLOW or mapping elements as findings instead of
treating them as silently supported. Mapping paths preserve the raw declared webMethods path as
authoritative; derived `PipelinePath` fields are lightweight flags, not schema resolution.

Later milestones will add fuller FLOW semantics, document/spec dependency extraction, Java metadata
expansion, adapter fixtures, trigger fixtures, process graphs, and Ollama input generation. Those are
intentionally outside M2b.
