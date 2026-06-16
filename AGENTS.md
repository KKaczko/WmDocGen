# Repository Guidance

This project builds an offline static-analysis tool for webMethods Integration Server packages.

Current accepted baseline is milestone M2b remediation: evidence-based FLOW mapping extraction with
policy-safe free-text handling, filtered raw attributes, and explicit disclosure policy snapshots on
top of the M2a call/dependency and observed control-flow model. Do not add Document Type resolution,
Java body analysis, adapter parsers, trigger parsers, process parsers, runtime simulation, Ollama
integration, or M3 work without a later explicit milestone approval.

Important constraints:

- Never execute code from analyzed packages.
- Never modify analyzed packages.
- Parse XML with the secure parser in `wm_doc.xmlsafe`.
- Treat unknown, malformed, unsupported, or backup files as explicit findings or inventory entries.
- Keep JSON, Markdown, and DOT outputs deterministic.
- Do not expose secret values from package files.
