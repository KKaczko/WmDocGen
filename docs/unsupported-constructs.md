# Unsupported Constructs

Unsupported or only partially supported in M2b:

- Full FLOW execution semantics
- Full MAP operation semantics beyond observed evidence extraction
- Detailed data lineage across multiple maps and services
- Validation that mapped paths exist in document schemas
- Document/schema resolution for `rec_ref` and pipeline path document-reference markers
- MAP-specific DOT graphs
- Full `BRANCH` condition evaluation
- Full `LOOP` iteration simulation
- `REPEAT` semantics
- Runtime effects of `EXIT`
- Dynamic service invocation resolution
- Document reference dependency extraction
- Java service body decoding or analysis
- JDBC Adapter Services
- Universal Messaging triggers
- JMS triggers
- Schedulers
- Process models
- Runtime-only Integration Server configuration
- Ollama documentation generation

M2b extracts static `INVOKE` and `MAPINVOKE` targets when a literal `SERVICE` attribute is present.
Targets that are not present in the analyzed snapshot are retained as unresolved call occurrences
and unresolved unique dependencies with source evidence.

M2b parses observed `EXIT` elements into typed FLOW nodes. Unknown EXIT shapes remain parsed but also
produce explicit findings.

M2b treats `MAP` as a structural container so nested `MAPINVOKE` calls can be positioned in the
ordered FLOW tree. It extracts typed evidence for observed `MAPCOPY`, `MAPSET`, `MAPDELETE`,
`MAPSOURCE`, `MAPTARGET`, and `DATA` shapes. Unknown mapping children, missing endpoints, malformed
paths, unsupported literal encodings, orphan metadata, or ambiguous transformer directions produce
explicit findings.

Literal values default to redacted output. Even when literal inclusion is enabled, secret-like
mapping contexts still block literal value disclosure. Free-text policy applies before canonical
serialization to supported free-text fields such as service descriptions, FLOW labels, display
labels, and mapping operation names. Raw attribute collections are filtered and are not an escape
hatch for free-text values.

Technical values remain visible when they are needed for static analysis. These include service
targets, pipeline paths, branch switches, loop arrays, exit attributes, validation flags, and
mapping endpoint attributes. Unknown attributes preserve name/source/presence and policy metadata,
but their raw values are not exposed by default.

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
