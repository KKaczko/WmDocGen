# wm-doc

`wm-doc` is an offline, deterministic static-analysis tool for Software AG / IBM webMethods
Integration Server package snapshots.

The current implemented milestone is **M3 for Document Type extraction and document-reference
graphs**. It discovers package and namespace artifacts, parses observed FLOW Service signatures,
extracts an ordered FLOW tree for observed structural nodes, separates static `INVOKE` call
occurrences from static `MAPINVOKE` transformer call occurrences, aggregates unique service-call
dependencies, extracts observed `MAPCOPY`, `MAPSET`, `MAPDELETE`, map source/target metadata, and
MAPINVOKE transformer bindings, extracts observed Document Types with ordered field trees, resolves
local document references by exact full name, classifies services with configurable glob rules, and
renders deterministic JSON, Markdown, and Graphviz DOT outputs.

This is not a claim of full webMethods 10.15 compatibility. `samples/OriginalSmall/OAAdapter` is the
primary 10.15 fixture; `samples/PGP` is a compatibility and discovery corpus with unknown upstream
provenance.

## Quick Start

```powershell
wm-doc scan samples --output out\inventory
wm-doc analyze samples --output out\m3-analysis
```

The scan command writes:

- `inventory.json`
- `fixture-inventory.md`

The analyze command writes:

- `analysis.json`
- `services/*.md`
- `documents/*.md`
- `graphs/dependencies.dot`
- `graphs/documents.dot`

`analysis.json` uses schema `analysis.v5`. In this schema, call occurrences preserve each concrete
`INVOKE` or `MAPINVOKE` site, unique service dependencies aggregate repeated calls by
`(caller, target, dependency kind)`, mapping evidence is exposed as `flow_maps`,
`mapping_operations`, and `transformer_bindings`, and document evidence is exposed as
`document_types`, `document_reference_occurrences`, `document_dependencies`, and
`service_document_dependencies`.

`graphs/dependencies.dot` remains the service-call dependency graph: one edge per unique static
service dependency with occurrence counts, not pipeline mappings. `graphs/documents.dot` contains
unique document-to-document `REFERENCES_DOCUMENT` edges and unresolved document nodes when observed.
Each document Markdown page includes the active disclosure policy snapshot used for the run.

Literal extraction defaults to `redact`, while free-text metadata defaults to `include`. The secret
guard still redacts secret-like literal and free-text contexts even when inclusion is explicitly
enabled. Free-text policy is applied before canonical serialization, and raw attribute collections
are filtered so they cannot bypass the configured policy.

M3 keeps document parsing evidence-based. It preserves raw field types, raw dimensions, source
references, and exact declared `rec_ref` targets; it does not validate mapping paths against document
schemas or infer business meaning from field names.

M3 hardening reports `MALFORMED_NESTED_RECORD` only for demonstrably malformed nested record
containers, such as non-array `rec_fields` metadata or non-record children inside a `rec_fields`
array. Empty record fields are allowed. `UNSUPPORTED_DOCUMENT_METADATA` reports structurally valid
metadata that is preserved as policy-controlled evidence but not yet interpreted semantically.

The tool works offline, treats analyzed packages as read-only, never connects to Integration Server,
and never executes analyzed Java or FLOW code.

## Development

The project is configured for Python 3.12+, `uv`, `pytest`, `ruff`, and `mypy`.

```powershell
uv run pytest
uv run ruff check .
uv run mypy
```

If `uv` is not installed, install it first or run the equivalent tools in a Python environment with
the dependencies from `pyproject.toml`.
