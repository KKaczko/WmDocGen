# Unsupported Constructs

Unsupported or only partially supported in M7:

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
- Dynamic service invocation resolution beyond explicit Java/FLOW findings
- Specification IR and specification document-reference dependency modeling
- Package dependency graph extraction
- Document default/fixed value extraction
- Recursive document expansion
- Business meaning inference from document or field names
- Broad Java external-effect classification
- Java helper method/body effect analysis
- Java execution, compilation, class loading, reflection modeling, or full semantic analysis
- Detailed JDBC Adapter Service parsing
- JDBC SQL, table, view, procedure, connection-alias, or database-resource extraction
- Adapter service family semantics beyond opaque service identity
- Universal Messaging triggers
- JMS triggers
- Schedulers
- Native webMethods BPM/process-model parsing
- Automatic business process discovery from technical graph shape
- Process include/exclude, stop-at, tag, owner, system, and maximum-depth catalog options
- Process-to-process dependency semantics
- Process-to-process overview graphs
- Interactive graph viewers, Mermaid output, JavaScript graph rendering, and static-site framework
  generation
- Runtime-only Integration Server configuration
- Ollama documentation generation

M5-lite keeps parseable service artifacts with explicit unsupported `svc_type` values, after
surrounding whitespace is trimmed, as `OPAQUE` services. Missing, empty, whitespace-only,
malformed, or non-scalar service-type metadata is not promoted to a service. Opaque services can
resolve exact incoming calls and appear in the service dependency graph, but their
implementation-specific body is not interpreted. The analyzer does not infer database, messaging,
scheduler, trigger, process, file, network, or other external behavior from an opaque service.

M6 supports only user-maintained `processes.yml` catalog declarations. Declared entrypoints must be
exact canonical service full names, and traversal follows only resolved local service dependencies.
Technical entrypoint candidates are labeled as technical roots and never promoted to business
processes. M6 does not parse native BPM/process-model artifacts, infer process descriptions, create
external-system nodes, or assign primary process ownership to services.

M7 supports optional Graphviz-derived SVG/PNG rendering only for DOT graphs already produced by the
canonical renderers. DOT remains the graph contract. The tool does not install Graphviz, edit DOT
for renderer compatibility, render Mermaid, create JavaScript viewers, generate ZIP/site bundles, or
infer new graph semantics from rendered images. It validates only the Graphviz SVG/PNG outputs it
publishes; arbitrary user-supplied image parsing and repair are out of scope. Rendering failures are
publishing failures, not analysis findings.

Generated-output cleanup is likewise publishing hygiene, not package analysis. It is limited to the
known generated output files/directories and does not attempt to classify, migrate, or delete
arbitrary user-managed output-root content.

M3 extracts static `INVOKE` and `MAPINVOKE` targets when a literal `SERVICE` attribute is present.
Targets that are not present in the analyzed snapshot are retained as unresolved call occurrences
and unresolved unique dependencies with source evidence.

Service dependency resolution is keyed by canonical `namespace:service` identity within the current
analysis result. Duplicate canonical service names across packages are an existing limitation and
are not redesigned in M5-lite; package-scoped resolution requires a separate milestone.

M4a extracts a narrow, deterministic Java Service static-analysis slice. It associates Java Service
metadata with generated source, checks the matched method against `java.frag` with normalized tokens,
extracts imports, referenced types, observed `IDataUtil.get*`, `put`, and `remove` calls, and records
narrowly supported `Service.doInvoke` sites. It analyzes only the matched service method for each
Java Service; sibling methods and helper classes do not contribute service behavior. The complete
source method must be a direct generated-class method with the exact service name, `static`, `void`,
and exactly one `IData` parameter. Unsupported same-name method signatures fall back to `java.frag`
and emit `JAVA_SOURCE_METHOD_SIGNATURE_UNSUPPORTED`.

M4a does not promote supported-looking Java API sites inside lambda bodies, anonymous-class methods,
or local-class bodies as direct service facts. Such sites are reported with bounded
`JAVA_NESTED_EXECUTABLE_BODY_SKIPPED` findings when observed. This is a limitation of the M4a
control-flow/callback model and does not imply that nested code never executes. Normal service-method
control blocks remain analyzed.

Malformed or unbalanced complete-source class/method structure emits `JAVA_SOURCE_PARTIAL_PARSE`
and uses `java.frag` fallback when available. `JAVA_SOURCE_METHOD_NOT_FOUND` is reserved for
reliably parsed source where no compatible direct service method exists.

Referenced Java type extraction covers imported types observed in the direct service method. Fully
qualified non-imported type expressions such as `java.nio.file.Path` are explicitly deferred in
M4a; the tool does not use loose dotted-name matching.

M4a promotes only statically confirmed Java invocation targets into call occurrences, unique
dependencies, and `graphs/dependencies.dot`. Dynamic or partially static Java targets remain
findings/evidence and do not create guessed dependency edges.

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

Malformed XML parser messages are sanitized before canonical serialization. Findings keep the
relative `SourceReference.path` and safe parser reason, but do not print absolute workspace paths,
temporary directories, user names embedded in paths, file URLs, raw XML, or invented `source_node`
values when the XML structure could not be parsed.

Technical values remain visible when they are needed for static analysis. These include service
targets, pipeline paths, branch switches, loop arrays, exit attributes, validation flags, and
mapping endpoint attributes. Unknown attributes preserve name/source/presence and policy metadata,
but their raw values are not exposed by default.

Document Markdown pages render the active disclosure policy snapshot: free-text mode, literal mode,
secret-guard enabled state, and secret-guard strategy. This does not add support for document
default/fixed-value extraction; those values remain deferred and are treated as unsupported metadata
if encountered.

Service Markdown pages render analysis support status and a bounded incoming `Called By` section
from resolved static dependency evidence. Opaque service pages state that the service was identified
but implementation-specific analysis was not performed. Java Markdown pages render source
consistency, declared signatures, observed pipeline accesses, Java invocation sites, imports,
referenced types, findings, and source evidence. They do not print complete Java bodies, decoded
`java.frag` bodies, raw token streams, arbitrary Java literals, or absolute local paths.

M6 process Markdown renders user-authored process names/descriptions, generated reachability
summaries, service membership, process dependency edges, unresolved process calls, document
relationships, and limitations. It links to existing service and document pages instead of copying
their full details. Unresolved process-document targets remain visible as technical identifiers but
are not linked to placeholder pages. Process DOT graphs contain member services, entrypoint styling,
opaque styling, and optional unresolved terminal leaves only.

Known disclosure limitations:

- Static path and target names can contain business words or secret-like field names. They are
  retained as technical evidence, not interpreted as secret values.
- Secret detection is deterministic and based on supported metadata plus name/context fallback
  heuristics. It can produce false positives for benign fields and false negatives for secrets that
  do not carry recognizable metadata or names.

Unsupported files currently include PGP compiled Java classes, key files, public resources, Eclipse
metadata, and config files. Inventory records their paths and sizes only; it does not render file
contents. PGP generated Java source is read only as the M4a Java Service parsing surface.

Observed but not interpreted uppercase FLOW elements currently produce `UNSUPPORTED_FLOW_ELEMENT`
findings. In the current OAAdapter fixture, generic unsupported findings are no longer emitted for
structural `MAP` or the supported observed `EXIT` shape.
