# Architecture

M1 implements package/artifact inventory plus a FLOW Service proof of concept.

Subsystems:

- Discovery locates package roots, namespace folders, and artifact file combinations.
- Secure XML parsing lives in `wm_doc.xmlsafe` and rejects DTD/entity declarations.
- `Values` parsing extracts safe metadata from `manifest.v3`, `node.idf`, and `node.ndf`.
- Service analysis in `wm_doc.analysis` parses observed FLOW Service signatures and `flow.xml`
  structures without executing package code.
- Classification in `wm_doc.config` applies deterministic, case-insensitive glob rules. `neverImportant`
  rules take precedence over important service rules.
- Dependency resolution is exact-name only. It resolves static `INVOKE` and `MAPINVOKE` targets to
  discovered FLOW or Java Service metadata and keeps unresolved targets as explicit IR objects.
- IR models in `wm_doc.ir` preserve source references, confidence basis, finding statuses,
  classifications, dependency edges, and unresolved dependencies.
- Renderers produce deterministic inventory JSON/Markdown and deterministic analysis JSON,
  per-service Markdown, and Graphviz DOT.
- The CLI exposes `wm-doc scan` and `wm-doc analyze`.

The M1 FLOW parser is feature-based. It interprets only the observed structures needed for the POC:
`FLOW`, `SEQUENCE`, `BRANCH`, `LOOP`, `REPEAT`, `INVOKE`, and `MAPINVOKE`. It records other observed
uppercase FLOW elements as findings instead of treating them as silently supported.

Later milestones will add fuller FLOW semantics, document/spec dependency extraction, Java metadata
expansion, adapter fixtures, trigger fixtures, process graphs, and Ollama input generation. Those are
intentionally outside M1.
