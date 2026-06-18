# wm-doc

`wm-doc` is an offline, deterministic static-analysis tool for Software AG / IBM webMethods
Integration Server package snapshots.

The current implemented milestone is **M6 for user-maintained process documentation** on top of
the M5-lite opaque service inventory baseline. It discovers package and namespace artifacts, parses
observed FLOW Service signatures, extracts ordered FLOW and mapping evidence, extracts observed
Document Types with ordered field trees, resolves local document references by exact full name,
performs source-first Java Service analysis, and preserves parseable unsupported service artifacts
as opaque services. Opaque services keep identity, trimmed source `svc_type`, safe `node_comment`,
signatures, source evidence, and exact incoming dependency resolution without interpreting
implementation details. M6 adds optional `processes.yml` business process declarations, exact
entrypoint validation, deterministic reachability over resolved service dependencies, technical
entrypoint candidates, process Markdown, and per-process DOT graphs.

This is not a claim of full webMethods 10.15 compatibility. `samples/OriginalSmall/OAAdapter` is the
primary 10.15 fixture; `samples/PGP` is a compatibility and discovery corpus with unknown upstream
provenance.

## Quick Start

```powershell
wm-doc scan samples --output out\inventory
wm-doc analyze samples --output out\m6-analysis
wm-doc analyze samples --processes-file processes.yml --output out\m6-process-analysis
```

The scan command writes:

- `inventory.json`
- `fixture-inventory.md`

The analyze command writes:

- `analysis.json`
- `index.md`
- `entrypoints.md`
- `services/*.md`
- `documents/*.md`
- `graphs/dependencies.dot`
- `graphs/documents.dot`
- `processes/*.md` and `graphs/processes/*.dot` when process definitions are declared

Its completion output reports analyzed service counts, support-status counts, opaque description
counts, promoted call occurrence counts, unique service dependency counts, process counts,
entrypoint validation counts, technical candidate counts, process memberships, process edges, and
unresolved process calls. The `Processes with findings` metric is the number of declared process
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
and never executes analyzed Java or FLOW code. M6 also does not compile Java source, load
classes, perform broad Java external-effect classification, analyze helper method bodies as service
behavior, or parse JDBC, SQL, database resources, connection aliases, UM/JMS, triggers, schedulers,
or native BPM/process-model definitions. M6 remains pending a final acceptance re-audit after the
link-rendering remediation.

## Development

The project is configured for Python 3.12+, `uv`, `pytest`, `ruff`, and `mypy`.

```powershell
uv run pytest
uv run ruff check .
uv run mypy
```

If `uv` is not installed, install it first or run the equivalent tools in a Python environment with
the dependencies from `pyproject.toml`.
