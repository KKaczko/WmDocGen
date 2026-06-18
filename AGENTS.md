# Repository Guidance

This project builds an offline static-analysis tool for webMethods Integration Server packages.

Current implementation milestone is M6: user-maintained process catalog and deterministic process
documentation on top of the accepted M5-lite opaque service inventory. M4a associates Java Services with generated source under
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

Do not add M4b, detailed JDBC/M5, native BPM process parsing, or later work without later explicit
milestone approval. In particular, do not add broad Java external-effect classification, adapter
parsers, trigger parsers, runtime simulation, Ollama integration, snapshot diffing, Java execution,
Java compilation, or Java class loading.

Important constraints:

- Never execute code from analyzed packages.
- Never modify analyzed packages.
- Parse XML with the secure parser in `wm_doc.xmlsafe`.
- Keep XML parser diagnostics disclosure-safe: findings use relative `SourceReference.path` for
  location and must not repeat absolute local paths in messages.
- Treat unknown, malformed, unsupported, or backup files as explicit findings or inventory entries.
- Keep JSON, Markdown, and DOT outputs deterministic.
- Do not expose secret values from package files.
- Do not serialize complete Java bodies, decoded `java.frag` bodies, raw token streams, arbitrary
  Java string literals, absolute local paths, or wrapper-only source coordinates.
