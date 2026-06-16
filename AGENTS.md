# Repository Guidance

This project builds an offline static-analysis tool for webMethods Integration Server packages.

Current accepted baseline is milestone M3 hardening: evidence-based Document Type extraction,
document field trees, exact local `rec_ref` resolution, service-document dependency extraction from
observed signatures, deterministic document Markdown with active disclosure policies, explicit
`MALFORMED_NESTED_RECORD` and `UNSUPPORTED_DOCUMENT_METADATA` findings, and a document-reference DOT
graph on top of the M2b FLOW mapping and disclosure model. Do not add Java body analysis, adapter
parsers, trigger parsers, process parsers, runtime simulation, Ollama integration, snapshot diffing,
or M4 work without a later explicit milestone approval.

Important constraints:

- Never execute code from analyzed packages.
- Never modify analyzed packages.
- Parse XML with the secure parser in `wm_doc.xmlsafe`.
- Treat unknown, malformed, unsupported, or backup files as explicit findings or inventory entries.
- Keep JSON, Markdown, and DOT outputs deterministic.
- Do not expose secret values from package files.
