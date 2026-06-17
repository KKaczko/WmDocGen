# Repository Guidance

This project builds an offline static-analysis tool for webMethods Integration Server packages.

Current accepted baseline is milestone M4a: source-first deterministic Java Service static analysis
on top of M3 hardening. M4a associates Java Services with generated source under `code/source`,
checks each matched method against `java.frag` with normalized Java tokens, extracts imports,
referenced types, observed pipeline READ/WRITE/REMOVE accesses, and narrowly supported static or
dynamic `Service.doInvoke` sites, and integrates only statically confirmed Java calls into service
dependencies. M4a acceptance remediation requires the generated service method to be a direct
`static void` method with exactly one `IData` parameter, excludes lambda/anonymous/local nested
executable bodies from direct service evidence, and reports malformed source structure explicitly.
The next required gate is an M4a re-audit.

Do not add M4b or M5 work without later explicit milestone approval. In particular, do not add
broad Java external-effect classification, adapter parsers, trigger parsers, process parsers,
runtime simulation, Ollama integration, snapshot diffing, Java execution, Java compilation, or Java
class loading.

Important constraints:

- Never execute code from analyzed packages.
- Never modify analyzed packages.
- Parse XML with the secure parser in `wm_doc.xmlsafe`.
- Treat unknown, malformed, unsupported, or backup files as explicit findings or inventory entries.
- Keep JSON, Markdown, and DOT outputs deterministic.
- Do not expose secret values from package files.
- Do not serialize complete Java bodies, decoded `java.frag` bodies, raw token streams, arbitrary
  Java string literals, absolute local paths, or wrapper-only source coordinates.
