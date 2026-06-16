# Unsupported Constructs

Unsupported or only partially supported in M3:

- Full FLOW execution semantics
- Full MAP operation semantics beyond observed evidence extraction
- Detailed data lineage across multiple maps and services
- Validation that mapped paths exist in document schemas
- Schema resolution for pipeline path document-reference markers
- MAP-specific DOT graphs
- Full `BRANCH` condition evaluation
- Full `LOOP` iteration simulation
- `REPEAT` semantics
- Runtime effects of `EXIT`
- Dynamic service invocation resolution
- Specification IR and specification document-reference dependency modeling
- Package dependency graph extraction
- Document default/fixed value extraction
- Recursive document expansion
- Business meaning inference from document or field names
- Java service body decoding or analysis
- JDBC Adapter Services
- Universal Messaging triggers
- JMS triggers
- Schedulers
- Process models
- Runtime-only Integration Server configuration
- Ollama documentation generation

M3 extracts static `INVOKE` and `MAPINVOKE` targets when a literal `SERVICE` attribute is present.
Targets that are not present in the analyzed snapshot are retained as unresolved call occurrences
and unresolved unique dependencies with source evidence.

M3 parses observed `EXIT` elements into typed FLOW nodes. Unknown EXIT shapes remain parsed but also
produce explicit findings.

M3 treats `MAP` as a structural container so nested `MAPINVOKE` calls can be positioned in the
ordered FLOW tree. It extracts typed evidence for observed `MAPCOPY`, `MAPSET`, `MAPDELETE`,
`MAPSOURCE`, `MAPTARGET`, and `DATA` shapes. Unknown mapping children, missing endpoints, malformed
paths, unsupported literal encodings, orphan metadata, or ambiguous transformer directions produce
explicit findings.

M3 extracts observed Document Types from `record/node_type=record` artifacts, preserves ordered field
trees, maps only observed field types and dimensions, and resolves `rec_ref` values only by exact
local full-name match. Missing `rec_ref`, unresolved targets, unknown field types, invalid
dimensions, duplicate sibling field names, malformed metadata, and document cycles produce explicit
findings.

M3 hardening adds two document-specific findings:

- `MALFORMED_NESTED_RECORD` has `WARNING` severity and is emitted only for structurally incompatible
  nested-record metadata: non-array `rec_fields` metadata or non-record direct children inside a
  `rec_fields` array. Empty record fields are not considered malformed by themselves.
- `UNSUPPORTED_DOCUMENT_METADATA` has `INFO` severity and is emitted for structurally valid document
  or field metadata that the current IR does not interpret. Repeated occurrences aggregate
  deterministically and retain bounded source samples. Metadata values remain policy-controlled and
  are not printed in findings.

Literal values default to redacted output. Even when literal inclusion is enabled, secret-like
mapping contexts still block literal value disclosure. Free-text policy applies before canonical
serialization to supported free-text fields such as service descriptions, FLOW labels, display
labels, and mapping operation names. Raw attribute collections are filtered and are not an escape
hatch for free-text values.

Technical values remain visible when they are needed for static analysis. These include service
targets, pipeline paths, branch switches, loop arrays, exit attributes, validation flags, and
mapping endpoint attributes. Unknown attributes preserve name/source/presence and policy metadata,
but their raw values are not exposed by default.

Document Markdown pages render the active disclosure policy snapshot: free-text mode, literal mode,
secret-guard enabled state, and secret-guard strategy. This does not add support for document
default/fixed-value extraction; those values remain deferred and are treated as unsupported metadata
if encountered.

Known disclosure limitations:

- Static path and target names can contain business words or secret-like field names. They are
  retained as technical evidence, not interpreted as secret values.
- Secret detection is deterministic and based on supported metadata plus name/context fallback
  heuristics. It can produce false positives for benign fields and false negatives for secrets that
  do not carry recognizable metadata or names.

Unsupported files currently include PGP Java source/classes, key files, public resources, Eclipse
metadata, and config files. Inventory records their paths and sizes only; it does not render file
contents.

Observed but not interpreted uppercase FLOW elements currently produce `UNSUPPORTED_FLOW_ELEMENT`
findings. In the current OAAdapter fixture, generic unsupported findings are no longer emitted for
structural `MAP` or the supported observed `EXIT` shape.
