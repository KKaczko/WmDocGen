# wm-doc

`wm-doc` is an offline, deterministic static-analysis tool for Software AG / IBM webMethods
Integration Server package snapshots.

The current implemented milestone is **M8c for structured Ollama business enrichment** on top of
the M6 process documentation and M5-lite opaque service inventory baselines. It discovers package and namespace artifacts, parses
observed FLOW Service signatures, extracts ordered FLOW and mapping evidence, extracts observed
Document Types with ordered field trees, resolves local document references by exact full name,
performs source-first Java Service analysis, and preserves parseable unsupported service artifacts
as opaque services. Opaque services keep identity, trimmed source `svc_type`, safe `node_comment`,
signatures, source evidence, and exact incoming dependency resolution without interpreting
implementation details. M6 adds optional `processes.yml` business process declarations, exact
entrypoint validation, deterministic reachability over resolved service dependencies, technical
entrypoint candidates, process Markdown, and per-process DOT graphs. M7 keeps those DOT graphs
canonical and can optionally render derived SVG/PNG graph views for publishable Markdown sites.
M8a performs the complete accepted M7 technical analysis first, then optionally limits publication
to one focused service, namespace, package, or process scope. M8b consumes focused M8a
`analysis.json` and `scope.json` artifacts and emits a bounded, auditable
`business-context.v1` package for local model use. M8c consumes that context pack through an
explicit command, calls a local Ollama provider for a small internal structured draft, validates
that draft against context evidence IDs, and then builds the final app-owned
`business-result.v1` plus deterministic business Markdown. M8c does not change package analysis,
focused publication, context generation, or canonical analysis/context schemas.

This is not a claim of full webMethods 10.15 compatibility. `samples/OriginalSmall/OAAdapter` is the
primary 10.15 fixture; `samples/PGP` is a compatibility and discovery corpus with unknown upstream
provenance.

## Quick Start

```powershell
wm-doc scan samples --output out\inventory
wm-doc analyze samples --output out\m7-analysis
wm-doc analyze samples --verbose --output out\m7-analysis-full
wm-doc analyze samples --processes-file processes.yml --output out\m7-process-analysis
wm-doc analyze samples --processes-file processes.yml --render-graphs both --output out\m7-published
wm-doc analyze samples --target-service pgp.services.common:readConfig --dependency-depth 1 --output out\m8a-service-scope
wm-doc analyze samples --target-namespace pgp.services.common --dependency-depth 0 --output out\m8a-namespace-scope
wm-doc analyze samples --processes-file processes.yml --target-process pgp-key-lookup --dependency-depth all --output out\m8a-process-scope
wm-doc build-business-context --input out\m8a-service-scope --output out\m8a-service-scope\business-context
wm-doc ollama-test --ollama-url http://localhost:11434 --model llama3.1
wm-doc enrich-business --context out\m8a-service-scope\business-context\context.json --output out\m8a-service-scope\business --model llama3.1
```

The scan command writes:

- `inventory.json`
- `fixture-inventory.md`

The analyze command writes:

- `analysis.json`
- `index.md`
- `LIMITATIONS.md`
- `entrypoints.md`
- `services/*.md`
- `documents/*.md`
- `graphs/dependencies.dot`
- `graphs/documents.dot`
- `graphs/index.md`
- `processes/*.md` and `graphs/processes/*.dot` when process definitions are declared
- optional `*.svg` and/or `*.png` graph images when `--render-graphs` requests them

Each service page opens with a deterministic `## Summary` paragraph synthesised from the
signature, the ordered call occurrences and the platform effect catalog in `wm_doc.builtins`,
for example:

> Reads a file, closes a stream, parses XML text and converts XML into a document.
> Takes `userId` and returns `key`. Calls 1 local service(s) and 4 platform service(s).
> No explicit error handling.

Summaries restate analysed facts. No model is involved and no business meaning is inferred.
Platform (`pub.*` / `wm.*`) dependencies are labelled from a fixed catalog of documented
services; an uncatalogued platform service is reported as uncatalogued rather than guessed.

`wm-doc analyze --verbose` adds the full mapping tables, FLOW outline, call occurrences,
Java analysis and source-evidence detail. The default page carries the summary, identity,
signatures, dependencies, callers and processes.

Focused publication mode is selected by exactly one of `--target-service <namespace:service>`,
`--target-namespace <namespace-prefix>`, `--target-package <package-name>`, or
`--target-process <process-id>`. `--dependency-depth` accepts `0`, a positive integer, or `all`
and defaults to `all`. More than one selector, or repeating the same selector, is a validation
error in M8a v1.

M8a reduces generated documentation and graph scope. It does not reduce the initial parsing and
analysis cost. Focused runs still write full canonical `analysis.json` using schema `analysis.v8`.
They additionally write `scope.json` using `scope.v1`, `scope.md`, scoped `entrypoints.md`, scoped
service/document Markdown, `graphs/scope.dot`, optional `graphs/scope-documents.dot`, and selected
process pages/graphs only for `--target-process`. Focused mode does not write global
`graphs/dependencies.dot` or `graphs/documents.dot`.

The `build-business-context` command requires focused M8a output. It can read an output directory:

```powershell
wm-doc build-business-context --input out\m8a-service-scope --output out\m8a-service-scope\business-context
```

or explicit artifact paths:

```powershell
wm-doc build-business-context --analysis out\m8a-service-scope\analysis.json --scope out\m8a-service-scope\scope.json --output out\context
```

It writes `context.json` using schema `business-context.v1` and a deterministic
`context.md` preview. `analysis.json` remains the complete `analysis.v8` snapshot, while
`scope.json` remains the selected `scope.v1` publication subset. The context pack separates
canonical technical facts, approved process metadata, deterministic summaries, limitations,
unknowns, omissions, and evidence IDs. It is an input package for M8c enrichment, not business
documentation generated by a model.

The command validates that scoped dependency, document, process, and boundary facts still agree
with the referenced canonical analysis facts before publishing. It owns only `context.json` and
`context.md`; failed builds preserve the previous complete pair when present.

The `ollama-test` command validates local Ollama availability, model presence, structured JSON
support, and the M8c internal `business-draft.v1` contract without writing files. By default M8c
only accepts loopback HTTP Ollama URLs such as `http://localhost:11434`; non-loopback providers
require explicit `--allow-remote-provider`.

The `enrich-business` command requires a `business-context.v1` `context.json`, an explicit model,
and an output directory. It writes only `result.json` using schema `business-result.v2` and
`index.md` under that output directory. The generated result records model provenance without
provider URLs, raw prompts, raw responses, or chain-of-thought. The model does not generate final
IDs, status, provenance, validation metadata, or confidence enums. Instead it returns draft buckets:
`claims` become `SUPPORTED`, `inferences` become `INFERRED`, and draft `unknowns`/`limitations`
are merged with deterministic source unknowns and limitations. Claims must cite valid context
evidence IDs.

A claim that fails validation is discarded and reported rather than rejecting the whole
generation: cited-but-unknown evidence, evidence a section does not accept, no citation at all, or
an unsupported identifier each produce a `*_CLAIM_DISCARDED` limitation naming what was dropped and
why, while the remaining claims publish. Malformed drafts and unsafe text still fail the run.

Citing a valid evidence ID is not sufficient. Every claim is also checked against the identifiers
its cited evidence actually contains: a claim naming a service, document, field or proper noun that
no cited evidence supports is discarded, and the discarded names are reported as an
`UNGROUNDED_CLAIM_DISCARDED` limitation. Sentence-initial prose and acronyms are not treated as
identifiers, so ordinary wording is unaffected. There is no `CONFIRMED` confidence: the application
never asserts that it verified a model statement beyond this grounding check.

Output language defaults to `en`. Generating another language leads small local models to translate
identifiers that must be copied verbatim, which the grounding check then discards. Valid partial results exit successfully and remain labeled
`PARTIAL`; invalid drafts, unknown evidence IDs, unsafe text, provider errors, and output failures
exit non-zero without publishing a partial bundle.

M8c caches only validated normalized `business-result.v2` JSON. The cache key includes the raw
context hash, provider kind, model name and digest when available, prompt version, internal draft
schema version, final result schema, language, and generation parameters. Use `--refresh` to bypass
a cache read or `--no-cache` to disable cache reads and writes. The persisted result stays
byte-stable across cache hits; the CLI reports hit or miss.

Its completion output reports analyzed service counts, support-status counts, opaque description
counts, promoted call occurrence counts, unique service dependency counts, process counts,
entrypoint validation counts, technical candidate counts, process memberships, process edges, and
unresolved process calls. M7 also reports DOT graph count, SVG/PNG render counts, render failures,
and graph-index generation. The `Processes with findings` metric is the number of declared process
definitions carrying process-level findings, not the total number of global catalog findings.

`analysis.json` uses schema `analysis.v8`. In this schema, call occurrences preserve each concrete
FLOW `INVOKE`, FLOW `MAPINVOKE`, or statically confirmed Java invocation site. Unique service
dependencies aggregate repeated calls by `(caller, target, dependency kind)`. Mapping evidence is
exposed as `flow_maps`, `mapping_operations`, and `transformer_bindings`; document evidence is
exposed as `document_types`, `document_reference_occurrences`, `document_dependencies`, and
`service_document_dependencies`; Java evidence is exposed as `java_service_analyses`,
`java_imports`, `java_type_references`, `java_pipeline_accesses`, and
`java_invocation_occurrences`. M5-lite adds service `source_service_type`, `analysis_status`,
`description_status`, call/dependency `target_analysis_status`, and metrics for service kinds,
support statuses, opaque services, and resolved opaque targets. M6 adds top-level `processes`,
`process_entrypoints`, `process_service_memberships`, `process_dependency_edges`,
`process_unresolved_calls`, `process_document_relationships`, and
`technical_entrypoint_candidates`.

In focused mode, `analysis.json` describes the complete discovered snapshot. `scope.json` describes
the selected publication subset. Markdown and focused graphs describe the selected publication
subset. Scope membership is deterministic BFS over resolved unique service dependencies, while
unresolved, dynamic, unsupported, or depth-limited calls become explicit scope boundaries.

Graph rendering is disabled by default: `--render-graphs none`. Use `svg`, `png`, or `both` to ask
the CLI to render every generated DOT graph with Graphviz `dot`, resolved from `PATH` or
`--graphviz-dot`. Graphviz is optional and is not installed by `wm-doc`. When rendering is requested
and Graphviz is missing or rejects a graph, canonical analysis, Markdown, and DOT files are still
written, successful graph assets remain linked, diagnostics are path-scrubbed and secret-redacted,
and the CLI exits non-zero. Rendered SVG is parsed as XML, stripped of Graphviz's external DTD
declaration and comments, and rejected when unsafe elements, event handlers, external links, or
absolute local paths are present. Rendered PNG must be structurally valid PNG data with valid chunks,
image dimensions, IDAT data, IEND, and CRCs.

Before writing analysis output, `wm-doc analyze` cleans only its managed generated locations:
`analysis.json`, `index.md`, `entrypoints.md`, `scope.json`, `scope.md`, `services`,
`documents`, `processes`, and `graphs`. Shape conflicts at those paths are replaced, unrelated
files under the output root are preserved, and symlinks at managed paths are unlinked rather than
followed. Cleanup and Graphviz diagnostics are bounded and scrub secret-like keys such as
`password`, `passwd`, `token`, `access_token`, `api-key`, and bearer authorization values before
CLI output.

If `--processes-file` is omitted, `wm-doc analyze` looks for `processes.yml` under the scan root.
Default absence is normal and produces no finding. A process catalog must use `version: 1`, stable
safe process IDs, user-authored names, optional policy-controlled descriptions, and exact canonical
service full names as entrypoints. Technical entrypoint candidates are generated from services with
zero incoming resolved local dependencies; they are not confirmed business process entrypoints.
Per-process Markdown separates `Declared Entrypoints` (the user-authored catalog values) from
`Entrypoint Validation` (the exact static resolution status). Process document relationships link to
generated document pages only when the canonical document is resolved and present in the generated
output; unresolved document targets remain visible as technical identifiers marked `UNRESOLVED` and
are not linked.

`graphs/dependencies.dot` remains the service-call dependency graph: one edge per unique static
service dependency with occurrence counts, not pipeline mappings. `graphs/documents.dot` contains
unique document-to-document `REFERENCES_DOCUMENT` edges and unresolved document nodes when observed.
DOT files remain the canonical graph contract. `graphs/index.md` lists every DOT graph and links
derived SVG/PNG assets only when those files were successfully rendered. Process pages always link
their DOT graph and show an SVG preview when available, otherwise PNG when available.
Each document Markdown page includes the active disclosure policy snapshot used for the run.
Each Java Service Markdown page includes source consistency, declared signatures, observed pipeline
accesses, Java invocation sites, imports, referenced types, findings, and source evidence without
printing Java bodies or decoded fragments.
Opaque service Markdown pages clearly state that the artifact was identified as a service but its
implementation-specific format was not analyzed. They do not claim absence of database, messaging,
scheduler, process, file, network, or other external behavior.
All service Markdown pages include a deterministic `Called By` section derived from resolved static
FLOW and Java service dependencies plus a bounded `Processes` section when process membership is
declared. Document pages include process reference sections derived from process/document
relationships. Generated Markdown link integrity is covered by regression tests for no-catalog,
fixture-catalog, synthetic unresolved-document, and free-text disclosure-mode outputs.

M4a trusts complete source as the behavioral authority only when the matched service method belongs
directly to the verified generated service class and has the supported generated shape:
`static void serviceName(IData pipeline)`. The `IData` parameter may be the imported short name or
`com.wm.data.IData`, and harmless parameter annotations are accepted. Same-name methods with
unsupported signatures fall back to `java.frag` and emit
`JAVA_SOURCE_METHOD_SIGNATURE_UNSUPPORTED`; multiple compatible same-name methods emit
`JAVA_SOURCE_METHOD_AMBIGUOUS`.

Observed Java facts are extracted from the direct service-method body. M4a continues to analyze
normal Java control blocks such as `if`, loops, `try/catch`, `switch`, and `synchronized`, but it
does not promote supported-looking API sites inside lambda bodies, anonymous-class methods, or local
class bodies as direct service evidence. Those sites emit
`JAVA_NESTED_EXECUTABLE_BODY_SKIPPED` limitation findings. Malformed or unbalanced complete source
emits `JAVA_SOURCE_PARTIAL_PARSE` and falls back to `java.frag` when available.

Literal extraction defaults to `redact`, while free-text metadata defaults to `include`. The secret
guard still redacts secret-like literal and free-text contexts even when inclusion is explicitly
enabled. Free-text policy is applied before canonical serialization, and raw attribute collections
are filtered so they cannot bypass the configured policy.
Malformed XML diagnostics are sanitized before JSON, Markdown, or CLI-visible findings are emitted:
the parser reason remains, while the authoritative location stays in the relative
`SourceReference.path` instead of the message.

M3 keeps document parsing evidence-based. It preserves raw field types, raw dimensions, source
references, and exact declared `rec_ref` targets; it does not validate mapping paths against document
schemas or infer business meaning from field names.

M3 hardening reports `MALFORMED_NESTED_RECORD` only for demonstrably malformed nested record
containers, such as non-array `rec_fields` metadata or non-record children inside a `rec_fields`
array. Empty record fields are allowed. `UNSUPPORTED_DOCUMENT_METADATA` reports structurally valid
metadata that is preserved as policy-controlled evidence but not yet interpreted semantically.

M6 keeps declared signatures and observed Java pipeline behavior separate. A real
`IDataUtil.get(...)`, `put(...)`, or `remove(...)` access is retained as observed behavior even when
the field is not declared in the service signature. The current fixture baseline has 24 FLOW
Services, 11 Java Services, 0 opaque services, 108 FLOW call occurrences, 86 FLOW-derived unique
dependencies, 73 Java pipeline accesses, 0 Java invocation occurrences, 0 declared processes by
default, and 15 technical entrypoint candidates.

Fully qualified type usages without imports, such as `java.nio.file.Path`, remain an explicit M4a
limitation. The `java_type_references` count covers imported types referenced by the direct service
method, not every possible fully qualified type expression.

The tool works offline, treats analyzed packages as read-only, never connects to Integration Server,
and never executes analyzed Java or FLOW code. M8c also does not compile Java source, load
classes, perform broad Java external-effect classification, analyze helper method bodies as service
behavior, or parse JDBC, SQL, database resources, connection aliases, UM/JMS, triggers, schedulers,
native BPM/process-model definitions, Mermaid diagrams, JavaScript graph viewers, static-site
frameworks, ZIP archives, CI publishing definitions, RAG, cloud provider defaults, arbitrary
external documents, prompt editing, model fine-tuning, snapshot comparison, impact analysis,
persistent analysis caching, or partial/lazy parsing.

## Development

The project is configured for Python 3.12+, `uv`, `pytest`, `ruff`, and `mypy`.

```powershell
uv run pytest
uv run ruff check .
uv run mypy
```

If `uv` is not installed, install it first or run the equivalent tools in a Python environment with
the dependencies from `pyproject.toml`.
