# Repository Guidance

This project builds an offline static-analysis tool for webMethods Integration Server packages.

Current implementation milestone is M7: Gitea-ready graph publishing and publishable
documentation on top of the accepted M6 process catalog baseline. M4a associates Java Services with generated source under
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

Do not add M4b, detailed JDBC/M5, native BPM process parsing, or later work without later explicit
milestone approval. In particular, do not add broad Java external-effect classification, adapter
parsers, trigger parsers, runtime simulation, Ollama integration, snapshot diffing, Java execution,
Java compilation, Java class loading, Mermaid, JavaScript graph viewers, static-site frameworks, or
ZIP publishing.

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
- Do not serialize complete Java bodies, decoded `java.frag` bodies, raw token streams, arbitrary
  Java string literals, absolute local paths, or wrapper-only source coordinates.
