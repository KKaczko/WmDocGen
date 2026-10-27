# Repository Guidance

This project builds an offline tool that documents webMethods Integration Server packages
(built against 10.15): a deterministic technical documentation site, and one reviewed
description file per service drafted by a local Ollama model from facts the tool established.
The target production server has about 200 packages and 7,300 services (6,000 FLOW, 1,100
adapter services) and 9,600 document types.

Current milestone: M12 (approved by the repository owner). The earlier business-context /
business-enrichment path (`build-business-context`, `enrich-business`, `ollama-test`,
`business-context.v*`, `business-result.v*`) was removed in M12; do not reintroduce it.
M13 (owner approval): the interactive explorer PoC; see "Explorer" below.
M14 (owner approval): conditional FLOW logic and decision lineage; see "Conditional FLOW logic".

## Pipeline and modules

- Discovery (`discovery.py`): finds package roots without descending into a package once found,
  applies package selection (`config.PackageSelectionConfig`: include/exclude globs; `Wm*`,
  `Default` and `system_package=yes` skipped by default) and records excluded packages with a
  reason. Non-service namespace nodes keep their declared `node_type`.
- Analysis (`analysis.py`, `java_analysis.py`, `values.py`, `xmlsafe.py`): FLOW services (ordered
  FLOW tree incl. TRY/CATCH via `SEQUENCE FORM`, REPEAT via `<RETRY>`, maps, transformers;
  `DISABLED="true"` steps and mapping lines are left out and counted in `disabled_steps`),
  Java services (source-first, checked against `java.frag`; only statically confirmed
  `Service.doInvoke` calls become dependencies), opaque services (explicit unsupported `svc_type`:
  identity, signature and description; JDBC adapter services also their decoded
  configuration), document types, and specification signatures through `svc_spec`.
- Readers (`adapters.py`, `triggers.py`): the approved JDBC adapter decoder and trigger reader
  (see "Approved readers"); their results sit on `FlowService.adapter` and
  `NamespaceArtifact.adapter` / `.trigger`.
- Platform catalog (`builtins.py`, `data/platform_services.yml`): one-line description, effect
  family and optional data-effect inputs per `pub.*` / `wm.*` service, written for wm-doc (never
  copied documentation); `--platform-services` adds or overrides entries for one command.
- Facts (`effects.py`, `references.py`, `builtins.py`, `external_systems.py`): per service, the
  direct callers, entry points (artifacts whose node.ndf contains a service's exact name,
  `processes.yml`, uncalled callers), and data and systems touched (signature documents; platform
  calls with object and location read from the literal or mapped documented input field; JDBC
  adapter services with operation, tables and connection; other opaque callees with the
  connections their node.ndf names; calls leaving the analysed packages, named by
  `external-systems.yml`). Effects of local callees are included with the call chain. Entry
  points also include trigger details and legacy REST v1 handlers.
- Prompts (`pseudocode.py`, `callgraph.py`, `summarizer.py`): a per-service pseudo-code view,
  callee-first ordering (Tarjan SCC), context fitting and the name-grounding check.
- Descriptions (`service_docs.py`, `describer.py`, `disclosure.py`): description files, the
  describe/approve/status/export workflow, the shared validated model call (`AnswerSpec`,
  `ModelSession`), and the disclosure scan for model text.
- Overviews (`overviews.py`, `render/package_markdown.py`): deterministic package facts
  (entry points, services, own data effects, calls between packages), package pages, and the
  package and server overview files written by `overview`.
- Analysis cache (`analysis_cache.py`): reuses the last `AnalysisResult` of a packages
  directory while the tool version, configuration, `processes.yml` and every file's path,
  size and mtime are unchanged. Per-service call graphs (`render/service_graph.py`) are
  written only when `--render-graphs` asks for images.
- Providers (`ollama_provider.py`, `openai_compatible_provider.py`, `provider_probe.py`).
- Rendering (`render/`), `stats.py`, `shapes.py`, `scope_analysis.py` (focused publication).
  `call_targets.py` classifies how a call ends (resolved, platform, outside, unresolved,
  dynamic, unsupported) for scope boundaries and the explorer; `output_cleanup.py` removes
  managed output paths for `analyze` and `explorer build`.
- Explorer (`explorer/`, app source in `explorer-ui/`): see "Explorer".
- Conditional FLOW logic (`flow_semantics.py`, `flow_paths.py`, `flow_logic.py`,
  `flow_lineage.py`, later `flow_scenarios.py`): see "Conditional FLOW logic". Tests build FLOW
  services with `tests/support/flowxml.py` (test-only; `samples/` stays read-only).

## Contracts

- `analysis.json` is schema `analysis.v11`: each fact is stored once, on the service, package or
  document it belongs to. Server-wide lists (`AnalysisResult.call_occurrences`,
  `unique_dependencies`, `mapping_operations`, Java lists, `document_types`, ...) are derived
  properties, not serialized. Each package's `service_index` lists only its own services.
- Focused publication (`analyze --target-service|--target-namespace|--target-package|
  --target-process`, one selector, optional `--dependency-depth`) writes `scope.json` (`scope.v1`)
  and focused graphs; `analysis.json` stays complete.
- Service page headings `## Input Signature`, `## Called By` and `## Processes` are load-bearing
  for scoped publication string surgery and must exist in default and `--verbose` modes.
- Description files: `service-docs/<Package>/<namespace folders>/<service>.md` with front matter
  (`status` draft|approved, `model`, `facts_hash`, `text_hash`), a narrative, a Notes section the
  tool never writes, and a facts block between `wm-doc:facts` markers that is always refreshed.
  An approved narrative, or one whose text differs from `text_hash`, is never overwritten. No
  timestamps. Package and server overviews use the same format at `<Package>/_package.md`
  (`service: package:<Package>`) and `_server.md` (`service: server`); their facts hash covers
  the package or server facts without the Purpose lines sent as context.
- Model use is limited to `describe` and `overview`: one service, package or the server per
  prompt, sized to `--num-ctx`; every
  identifier-shaped name in the answer must occur in the facts sent; the disclosure scan must pass;
  one corrective retry; otherwise the answer is rejected. Only validated drafts are cached.
  Owner decision (M12): with `describe --keep-unverified`, an answer that passes the disclosure
  scan but still names things outside the facts after the retry is written as a draft marked
  `unverified_names` (front matter and a notice); it is never cached, is asked again on the
  next run, is not used as callee context, and approving it clears the mark.
  Owner decision (M12): `describe --detail brief|standard|thorough|deep` sets how much is
  written (thorough adds one request when the detailed flow leaves out calls that matter)
  and deep lets the model think first (only the final answer is read, the reasoning is never
  kept); `--instructions FILE` (describe and overview, at most 4,000 characters) appends
  the owner's own instructions to the fixed system prompt; they never override its rules.
  Timings are printed to the console only, never written to files.
  For adapter and other opaque services the tool, not the model, writes Main steps and Error
  handling.
- Facts are never inferred from names. Every data-effect row states how it is known. Artifact
  references are exact full-name matches only; no other value from those files is kept.
- Defaults: literal and free-text disclosure `include`, with the secret guard evaluated first in
  every mode; description language English.

## Approved readers (owner approval, M12, after checking real public 10.x packages)

- JDBC adapter decoder (`adapters.py`): decodes the binary `IRTNODE_PROPERTY` value of
  `AdapterService` services, `ConnectionData` connections and adapter notifications and keeps
  only an allow-list of fields: operation template, connection name, tables, adapter type, and
  for connections the datasource class (database product), database name and transaction type;
  for notifications the notification type, connection, table and published document. Server,
  host, port, user, password, URL and any other connection property are never read or kept.
- Trigger reader: `trigger_type` (JMS or webMethods messaging), JMS connection alias,
  destinations (name and queue/topic), subscribed document types and handler services.
- Legacy REST handlers: services named `_get`, `_post`, `_put`, `_patch`, `_delete` or
  `_default` are IS REST v1 endpoints at `/rest/<namespace as path>`.

## Explorer (owner approval, M13 PoC)

- `wm-doc explorer build|demo|serve`. `wm_doc.explorer` projects the in-memory analysis and
  existing facts into the `wm-doc-explorer.v1` contract (`explorer/contract.py`, schema in
  `docs/contracts/explorer.v1.schema.json`); the app never reads `analysis.json`. Core modules
  never import `wm_doc.explorer` (tested).
- Python owns all resolution and classification; the app only displays and walks emitted
  facts. All text is rendered as text (no HTML or Markdown rendering, no
  `dangerouslySetInnerHTML`); a strict CSP; no external requests. Literal values, designer
  comments, Notes, SQL and connection properties are never exported (a data effect known from
  a literal shows `(literal, not exported)`; branch condition values are the one exception,
  see "Conditional FLOW logic"); free text passes the
  disclosure scan or is withheld and counted.
- The output folder must not overlap the packages folder. Files are named by hashed IDs.
- The call graph (`graph.json`, `explorer-ui/src/domain/graph.ts`) walks only emitted
  edges and must reach exactly what focused publication reaches for the same service and
  depth (cross-language fixture test). It is bounded: depth 1-4, node limit 50/150/300,
  25 new neighbours per node ("+N more").
- `explorer-ui/` (React, TypeScript, Vite; exact dependency versions, `npm ci
  --ignore-scripts`) is a developer-only toolchain. Its build output
  `src/wm_doc/explorer/app/` is committed and must be rebuilt with every app change; the
  build is reproducible. Demos use `explorer demo` (synthetic packages) only.
- PoC plan: PR 1 search and service pages; PR 2 descriptions, effects and trust labels;
  PR 3 bounded dependency graph (React Flow, caps on depth, nodes and neighbours per node);
  PR 4 package explorer and scale checks.

## Conditional FLOW logic (owner approval, M14)

- Goal: explain which calls run under which BRANCH conditions, which paths are alternatives,
  where decision variables come from and how earlier responses feed later decisions. Static
  only: no runtime simulation, no evaluation of expressions or regular expressions.
- The logic is derived core facts computed on demand (like `effects.py`), never stored in
  `analysis.json`. Every derived fact carries a certainty (observed, derived, possible,
  unknown), a basis, and the id of the IS rule it rests on (`flow_semantics.py`, documented in
  `docs/flow-semantics.md`); conclusions resting on an assumed rule are shown as assumptions.
- Owner decisions (2026-10-25): branch condition values are shown in pages, prompts and the
  Explorer, subject to the free-text policy and the secret guard (`explorer build
  --condition-values exclude` opts out; MAPSET literals stay unexported in the Explorer); a
  called service's declared outputs are possible sources only, and calls between a definition
  and a decision are listed as a caveat; the owner checks the assumed rules on IS 10.15; AI
  descriptions return structured items that reference decision, case and call ids, the tool
  writes condition text, and answers are checked against the facts.
- A step after a BRANCH never inherits that BRANCH's conditions. "Comes from" wording requires
  exactly one observed origin on every path and no call in between; nothing is concluded from
  similar field names. A definition replaces earlier ones only when it certainly writes the
  field (`flow_lineage.py`); copies from a possibly absent field or one list element,
  transformer outputs, overwrite-off sets, declared callee outputs, `clearPipeline` (its
  `preserve` list may come from the pipeline) and lines with uninterpreted attributes keep the
  earlier ones possible.
- Description files show the decisions and their origins under `### Decisions` in the facts
  block (refreshed on every run, not part of the facts hash).
- The pseudo-code the model sees (every detail level, with notes and comments) and the facts
  hash of description files are frozen for the samples and a builder-made service by
  `tests/unit/test_flow_facts_golden.py`; change them only on purpose.
- Plan: stage 0 foundations; 1 call conditions and a Decisions section; 2 decision-variable
  lineage; 3 scenarios; 4 AI prompt and structured validation; 5 disclosure hardening
  (`analysis.v12`); 6 Explorer conditional flow; 7 conservative cross-service facts.

## Out of scope without explicit owner approval

Semantic parsers for REST/SOAP descriptor details beyond service references, other adapter
types' configuration, native BPM process models, runtime simulation, Java execution,
compilation or class loading, broad Java external-effect classification, non-Ollama or cloud model
providers, RAG or arbitrary external documents, a prompt editing UI (beyond the approved
`--instructions` file), fine-tuning, snapshot diffing,
Mermaid, JavaScript graph viewers or static-site frameworks other than the explorer, ZIP
publishing, a backend or database for the explorer.

## Important constraints

- Never execute code from analyzed packages.
- Never modify analyzed packages. Designer comment text is exported to files only.
- Parse XML with the secure parser in `wm_doc.xmlsafe`.
- Keep XML parser diagnostics disclosure-safe: findings use relative `SourceReference.path` for
  location and must not repeat absolute local paths in messages.
- Treat unknown, malformed, unsupported, or backup files as explicit findings or inventory entries.
- Keep JSON, Markdown, DOT and description-file outputs deterministic.
- Keep SVG/PNG as derived publishing artifacts; do not make them inputs to analysis. Normalize
  Graphviz SVG output, reject malformed or unsafe SVG/PNG output, and never serialize absolute
  Graphviz executable paths or raw Graphviz diagnostics containing secret-like values.
- Managed output cleanup is limited to generated root files and generated directories; unrelated
  output-root files must be preserved and symlinks unlinked rather than traversed.
- Keep cleanup, provider and Graphviz diagnostics bounded, relative/path-scrubbed, and redacted for
  key names such as `password`, `passwd`, `token`, `access_token`, `api-key`, and bearer values.
- Do not expose secret values from package files.
- Never persist raw prompts, raw model responses, provider URLs, auth material, chain-of-thought,
  or invalid model output (except the marked unverified drafts above, kept on request). A
  server token is read from the environment variable named by
  `--api-key-env`, never from a flag, and is only sent over https or to loopback.
- Developer `<COMMENT>` text from `flow.xml` is used in prompts only, through the free-text policy,
  and is not added to `analysis.json`.
- Do not serialize complete Java bodies, decoded `java.frag` bodies, raw token streams, arbitrary
  Java string literals, absolute local paths, or wrapper-only source coordinates.
