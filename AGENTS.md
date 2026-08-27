# Repository Guidance

This project builds an offline static-analysis tool for webMethods Integration Server packages.

Current implementation milestone is M9: readable deterministic documentation plus grounded
business enrichment, on top of the accepted M8c baseline.

M9 adds `src/wm_doc/builtins.py`, a fixed name-to-label catalog of documented webMethods platform
(`pub.*` / `wm.*`) services, and `src/wm_doc/render/service_summary.py`, which synthesises a
deterministic `## Summary` paragraph from the signature, the ordered call occurrences and that
catalog. Summaries restate analysed facts only; no model is involved and no business meaning is
inferred. The catalog is a static lookup, not an adapter, trigger or resource parser, and an
uncatalogued platform service is reported as uncatalogued rather than guessed.

M9 makes service Markdown summary-first. Mapping, FLOW-outline, call-occurrence, Java and
source-evidence detail moves behind `wm-doc analyze --verbose`. `## Mapping Deletes` is removed
because its rows only record pipeline cleanup. The repeated per-file limitations paragraph becomes
a single generated `LIMITATIONS.md`. The headings `## Input Signature`, `## Called By` and
`## Processes` are load-bearing for scoped publication string surgery and must exist in both modes.

M9 changes two defaults. Literal disclosure defaults to `include`, because blanket redaction hid
the filenames and flags a reader needs; the secret guard is evaluated before the disclosure mode and
still blocks secret-like literals in every mode. Business enrichment output language defaults to
`en`, because generating Polish caused a local model to translate identifiers it must copy verbatim.

M9 makes claim rejection non-fatal. A claim that cites a non-existent evidence id, cites evidence
its section does not accept, cites nothing, or names an identifier no cited evidence supports is
discarded and reported as an `UNGROUNDED_CLAIM_DISCARDED`, `UNCITED_CLAIM_DISCARDED`,
`UNKNOWN_EVIDENCE_CLAIM_DISCARDED`, or `MISSECTIONED_CLAIM_DISCARDED` limitation; the remaining
claims still publish. This replaces the earlier contract in which any of those rejected the whole
response, which repeatedly discarded multi-minute generations over one bad item. Malformed drafts
and unsafe generated text still reject the entire response and exit non-zero.

M9 widens claim sectioning. Narrative sections (`purpose`, `actors`, `triggers`, `outcomes`,
`systems`, `exceptions`) may now cite `DEPENDENCY` and document evidence. Withholding those left
`general` as the only section able to cite substantial evidence, which pushed models into it and
produced restatements of the dependency graph rather than business statements.

M9 grounds model claims. `business-result.v2` replaces the `CONFIRMED` confidence with `SUPPORTED`,
and a claim naming an identifier that no cited evidence supports is discarded and reported as an
`UNGROUNDED_CLAIM_DISCARDED` limitation. Confidence is no longer taken from the draft array a
statement appeared in alone. `business-context` no longer carries `DELETE` mapping operations.
`analysis.json` remains `analysis.v8` and `scope.json` remains `scope.v1`; summaries and platform
effect labels are render-time derivations and are never written into the canonical snapshot.

The previous milestone is M8c: structured local Ollama business enrichment on top of the
accepted M8b business-context baseline. M8a performs the complete M7 technical analysis first,
keeps `analysis.json` as the full `analysis.v8` snapshot, and then optionally limits generated
Markdown and focused graph publication through one selector. Focused publication reduces generated
documentation and graph scope; it does not reduce the initial parsing or analysis cost. M8b consumes
focused `analysis.json` and `scope.json` artifacts through `wm-doc build-business-context` and
writes bounded `business-context.v1` JSON plus a deterministic preview Markdown file. M8c consumes
that context through `wm-doc enrich-business`, calls local Ollama `/api/chat` with a small internal
`business-draft.v1` structured-output contract, validates draft text and evidence IDs, then builds
the final application-owned `business-result.v1` plus deterministic Markdown. The model never owns
final IDs, status, provenance, validation metadata, or confidence enums. M8c does not change package analysis,
`analysis.v8`, `scope.v1`, or `business-context.v1`. M4a
associates Java Services with generated source under
`code/source`, checks each matched method against `java.frag` with normalized Java tokens, extracts
imports, referenced types, observed pipeline READ/WRITE/REMOVE accesses, and narrowly supported
static or dynamic `Service.doInvoke` sites, and integrates only statically confirmed Java calls into
service dependencies.

M5-lite adds deterministic inventory for parseable service-like `node.ndf` artifacts whose
top-level `svc_type` is explicit after whitespace trimming but not a supported FLOW, Java, or
Specification type. These services are retained as `OPAQUE`, may resolve as exact service-call
targets, and expose only common metadata such as identity, trimmed source `svc_type`, safe
`node_comment`, and signatures. Do not infer database, adapter, trigger, scheduler, UM/JMS,
process, or external-resource behavior from opaque artifacts.

M6 adds optional `processes.yml` parsing, exact declared entrypoint validation, deterministic
process traversal over resolved service dependencies, technical entrypoint candidates, process
Markdown, top-level documentation index, and per-process DOT graphs. It does not parse native
webMethods BPM/process-model artifacts and does not infer business processes from technical root
candidates.

M7 keeps `analysis.json` at schema `analysis.v8` and keeps DOT files canonical. It adds optional
Graphviz-derived SVG/PNG publishing behind `wm-doc analyze --render-graphs`, a generated
`graphs/index.md`, stale generated-output cleanup, and Markdown links/previews suitable for Gitea.
Graphviz is an optional external executable, not a Python dependency or a default-analysis
requirement. Render failures must leave canonical analysis and DOT outputs available, report safe
relative diagnostics, and exit non-zero only when rendering was explicitly requested.
Managed output cleanup is limited to generated root files and generated directories. Shape conflicts
at those paths may be replaced, but unrelated output-root files must be preserved and symlinks must
be unlinked rather than traversed.

M8a focused publication supports exactly one selector per run: `--target-service`,
`--target-namespace`, `--target-package`, or `--target-process`, plus optional
`--dependency-depth`. Selector unions and repeated selectors are intentionally deferred. In focused
mode `scope.json` uses `scope.v1`; `analysis.json` remains the complete snapshot. Scoped outputs
use focused graph names such as `graphs/scope.dot` and do not write global
`graphs/dependencies.dot` or `graphs/documents.dot`.

Do not add M4b, detailed JDBC/M5, native BPM process parsing, cloud/RAG business generation, or
later work without later explicit
milestone approval. In particular, do not add broad Java external-effect classification, adapter
parsers, trigger parsers, runtime simulation, non-Ollama providers, cloud provider defaults, RAG,
arbitrary external documents, prompt editing UI, model fine-tuning, snapshot diffing, Java
execution, Java compilation, Java class loading, Mermaid, JavaScript graph viewers, static-site
frameworks, or ZIP publishing.

Important constraints:

- Never execute code from analyzed packages.
- Never modify analyzed packages.
- Parse XML with the secure parser in `wm_doc.xmlsafe`.
- Keep XML parser diagnostics disclosure-safe: findings use relative `SourceReference.path` for
  location and must not repeat absolute local paths in messages.
- Treat unknown, malformed, unsupported, or backup files as explicit findings or inventory entries.
- Keep JSON, Markdown, and DOT outputs deterministic.
- Keep SVG/PNG as derived publishing artifacts; do not make them inputs to analysis.
- Normalize Graphviz SVG output before publishing, reject malformed or unsafe SVG/PNG output, and
  never serialize absolute Graphviz executable paths or raw Graphviz diagnostics containing
  secret-like values.
- Keep cleanup and Graphviz failure diagnostics bounded, relative/path-scrubbed, and redacted for
  key names such as `password`, `passwd`, `token`, `access_token`, `api-key`, and bearer values.
- Do not expose secret values from package files.
- M8c must never persist raw prompts, raw model responses, provider URLs, auth material,
  chain-of-thought, or invalid model output. Cache only validated normalized `business-result.v1`.
- Do not serialize complete Java bodies, decoded `java.frag` bodies, raw token streams, arbitrary
  Java string literals, absolute local paths, or wrapper-only source coordinates.
