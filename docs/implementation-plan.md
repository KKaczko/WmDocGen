# Implementation Plan

## M0 Setup + Inventory

Implemented in this milestone:

- Python project skeleton
- Secure XML parser
- webMethods `Values` metadata reader
- Package root discovery
- Namespace folder and artifact grouping
- Active artifact, backup file, unsupported file, malformed XML, and provenance reporting
- Deterministic JSON and Markdown inventory output
- CLI command: `wm-doc scan`

Verification output:

- Generated `out/m0-inventory/inventory.json`
- Generated `out/m0-inventory/fixture-inventory.md`
- Detected packages: `OAAdapter`, `PGP`
- Detected active artifact counts: 24 FLOW Services, 11 Java Services, 8 Specifications,
  7 Document Types, 14 namespace folders, 1 manifest
- Detected helper backup files: 23
- Reported PGP provenance and package-name alias findings

Not implemented in M0:

- Full FLOW hierarchy parsing
- Static invoke extraction
- Classification
- DOT rendering
- Java body decoding or analysis
- Adapter, trigger, scheduler, process, or Ollama support

Each later milestone must be explicitly approved before implementation.

## Next Milestone Gate

M1 FLOW POC was explicitly approved and implemented.

## M1 FLOW Service Proof Of Concept

Implemented in this milestone:

- CLI command: `wm-doc analyze`
- Canonical M1 analysis IR for FLOW Services, signatures, containers, invokes, dependency edges,
  unresolved dependencies, classification results, and source references
- Secure parsing of observed `node.ndf` service signatures
- Secure parsing of observed `flow.xml` files without executing FLOW logic
- Extraction of observed FLOW containers: `FLOW`, `SEQUENCE`, `BRANCH`, `LOOP`, `REPEAT`
- Extraction of static `INVOKE` and `MAPINVOKE` targets from the `SERVICE` attribute
- Exact-name dependency resolution against discovered FLOW and Java Service metadata
- Unresolved dependency reporting for external, runtime, adapter, and `pub.*` targets
- Configurable case-insensitive glob classification with `neverImportant` precedence
- Deterministic outputs: `analysis.json`, per-service Markdown, and Graphviz DOT
- Tests for OAAdapter, PGP compatibility, malformed XML, missing `flow.xml`, unknown FLOW elements,
  unresolved invocations, deterministic rendering, classification, and XML security

Verification output:

- Generated `out/m1-analysis/analysis.json`
- Generated `out/m1-analysis/services/*.md`
- Generated `out/m1-analysis/graphs/dependencies.dot`
- Analyzed FLOW Services: 24
- Static dependency edges: 108
- Resolved edges: 49
- Unresolved edges: 59
- Primary OAAdapter service static invocations: 43
- Primary OAAdapter service unresolved invocations: 43
- PGP FLOW Services parsed by the same parser: 23

Not implemented in M1:

- Full MAP data-flow semantics
- Full BRANCH/LOOP/EXIT execution semantics
- Dynamic invocation discovery beyond explicit unresolved reporting when observed
- Document reference dependency extraction
- Java source decoding or Java body analysis
- Adapter, trigger, scheduler, process, or Ollama support

## Next Milestone Gate

M2a call/dependency model and control-flow semantics was explicitly approved and implemented.

## M2a Call/Dependency Model And Control-Flow Semantics

Implemented in this milestone:

- Analysis schema migration from `analysis.v1` to `analysis.v2`
- Split between concrete `call_occurrences` and aggregated `unique_dependencies`
- Dependency kinds: `INVOKE -> INVOKES`, `MAPINVOKE -> USES_TRANSFORMER`
- Ordered FLOW tree with typed nodes for `FLOW`, `SEQUENCE`, `BRANCH`, derived `BRANCH_CASE`,
  `LOOP`, structural `MAP`, `INVOKE`, `MAPINVOKE`, and `EXIT`
- Extraction of observed `SEQUENCE` attributes including `NAME`, `EXIT-ON`, `FORM`, and `TIMEOUT`
- Extraction of observed `BRANCH` attributes including `SWITCH`, `LABELEXPRESSIONS`, ordered cases,
  and directly observed `$default` labels
- Extraction of observed `LOOP` attributes including `NAME`, `IN-ARRAY`, optional `OUT-ARRAY`, and
  `TIMEOUT`
- Parsing of observed `EXIT` nodes with `FROM`, `SIGNAL`, and `FAILURE-MESSAGE`
- Explicit partial-support findings for deferred MAP internals: `MAPCOPY`, `MAPSET`, `MAPDELETE`,
  `MAPSOURCE`, `MAPTARGET`, and `DATA`
- Default DOT graph changed from occurrence edges to unique dependency edges with occurrence counts
- Per-service Markdown now includes FLOW overview, bounded FLOW outline, normal service calls, and
  transformer calls

Verification baseline:

- Analyzed FLOW Services: 24
- Call occurrences: 108
- `INVOKE` occurrences: 68
- `MAPINVOKE` occurrences: 40
- Unique dependencies: 86
- `INVOKES` unique dependencies: 61
- `USES_TRANSFORMER` unique dependencies: 25
- Resolved call occurrences: 49
- Unresolved call occurrences: 59
- Resolved unique dependencies: 45
- Unresolved unique dependencies: 41
- Primary OAAdapter call occurrences: 43
- Primary OAAdapter unique dependencies: 25
- Primary OAAdapter FLOW node counts: 32 `SEQUENCE`, 27 `BRANCH`, 2 `LOOP`, 9 `EXIT`,
  135 `MAP`, 13 `INVOKE`, and 30 `MAPINVOKE`

Not implemented in M2a:

- MAP data-flow semantics
- `MAPCOPY`, `MAPSET`, `MAPDELETE`, `MAPSOURCE`, `MAPTARGET`, or `DATA` operation summaries
- MAPINVOKE input/output mapping extraction
- Literal/free-text extraction policies
- Branch condition evaluation
- Loop iteration simulation
- Java source decoding or Java body analysis
- Adapter, trigger, scheduler, process, or Ollama support

## Next Milestone Gate

M2b FLOW mapping extraction and disclosure policies was explicitly approved and implemented.

## M2b FLOW Mapping Extraction And Disclosure Policies

Implemented in this milestone:

- Analysis schema migration from `analysis.v2` to `analysis.v3`
- Globally stable SHA-derived IDs for call occurrences, flow maps, mapping operations, and
  transformer bindings
- Canonical `FlowMap` records for observed `MAP` elements, including `MODE`, parent call
  references, raw attributes, structural paths, source evidence, and map-level source/target schema
  metadata summaries
- Typed mapping operations for observed `MAPCOPY`, `MAPSET` with child `DATA`, and `MAPDELETE`
- Lightweight `PipelinePath` parsing that preserves the declared raw path and only records simple
  features such as absolute paths, indexes, wildcards, and document-reference markers
- Literal disclosure policy configuration: `redact` by default, plus explicit `include` and `omit`
  modes
- Free-text disclosure policy configuration: `include` by default, plus `redact` and `omit` modes
- Secret guard for secret-like mapping contexts, which blocks literal value disclosure even under
  explicit include mode
- MAPINVOKE transformer bindings derived from child `MODE="INVOKEINPUT"` and
  `MODE="INVOKEOUTPUT"` maps
- Markdown mapping overview and bounded tables for copies, sets, deletes, and transformer bindings
- Continued dependency DOT behavior with unique dependency edges only
- Fixture and synthetic tests for mapping counts, literal policies, secret guard behavior,
  malformed mapping endpoints, unsupported DATA encodings, and deterministic outputs

Verification baseline:

- Analyzed FLOW Services: 24
- Call occurrences: 108
- Unique dependencies: 86
- `INVOKE` occurrences: 68
- `MAPINVOKE` occurrences: 40
- Unique `INVOKES` dependencies: 61
- Unique `USES_TRANSFORMER` dependencies: 25
- Resolved call occurrences: 49
- Unresolved call occurrences: 59
- Flow maps: 265
- Mapping operations: 568
- `COPY` operations: 297
- `SET` operations: 93
- `DELETE` operations: 178
- Transformer bindings: 198
- `INTO_TRANSFORMER` bindings: 132
- `FROM_TRANSFORMER` bindings: 66
- Primary OAAdapter maps: 135
- Primary OAAdapter mapping operations: 219
- Primary OAAdapter transformer bindings: 168

Not implemented in M2b:

- Document Type parsing or validation that mapped paths exist in schemas
- Full MAP data-lineage semantics beyond typed operation evidence
- MAP operation DOT graphs
- Branch condition evaluation
- Loop iteration simulation
- Java source decoding or Java body analysis
- JDBC Adapter Services
- Universal Messaging or JMS triggers
- Schedulers
- Process models
- Dynamic invocation resolution
- Ollama documentation generation

## Next Milestone Gate

M2b remediation was explicitly approved and implemented after acceptance audit found that free-text
policy coverage did not yet include FLOW labels or free-text-like attributes.

## M2b Remediation: Free-Text Disclosure And Policy Hardening

Implemented in this remediation:

- Analysis schema migration from `analysis.v3` to `analysis.v4`
- Policy-safe text metadata for service descriptions, FLOW labels, free-text `NAME` attributes,
  display labels, mapping operation names, and free-text-like attributes
- Filtered raw attributes so canonical IR no longer stores complete unfiltered XML attribute
  dictionaries
- Explicit extraction policy snapshot with literal mode, free-text mode, and enabled secret guard
  strategy version
- Deterministic secret guard for literal and free-text contexts under include and redact modes
- Mapping operation ordering fields with distinct meanings:
  service-local discovery `order`, containing-map `map_operation_order`, and
  `document_traversal_order`
- Markdown mapping overview with transformer input/output binding counts
- Tests for free-text redact/include/omit, secret guard behavior, raw-attribute bypass prevention,
  policy snapshot, ordering semantics, independent raw XML counts, and regression metrics

Verification baseline remains unchanged:

- Analyzed FLOW Services: 24
- Call occurrences: 108
- Unique dependencies: 86
- Unique `INVOKES` dependencies: 61
- Unique `USES_TRANSFORMER` dependencies: 25
- Flow maps: 265
- Mapping operations: 568, split into 297 `COPY`, 93 `SET`, and 178 `DELETE`
- Transformer bindings: 198, split into 132 `INTO_TRANSFORMER` and 66 `FROM_TRANSFORMER`

Not implemented in M2b remediation:

- Any M3 document/spec/package graph work
- Document Type parsing or schema-aware mapping validation
- Java body analysis
- Adapter, trigger, scheduler, process, Ollama, snapshot diff, or Integration Server connectivity

## Next Milestone Gate

M3 Document Type extraction and document-reference graph work was explicitly approved and
implemented.

## M3 Document Type Extraction And Document-Reference Graph

Implemented in this milestone:

- Analysis schema migration from `analysis.v4` to `analysis.v5`
- Canonical Document Type IR for observed `record/node_type=record` artifacts
- Document identity from `record/node_nsName`, with namespace-path fallback and mismatch findings
- Ordered document field trees with raw field types, canonical field types, raw dimensions,
  interpreted dimensions, source order, structural paths, display field paths, source references,
  technical metadata, policy-safe text metadata, and unknown metadata policy filtering
- Supported observed field types: `string`, `object`, `record`, and `recref`
- Supported observed dimensions: `0 -> SCALAR` and `1 -> LIST`
- Document reference occurrences from `recref` fields with `rec_ref`
- Service signature document reference occurrences from observed FLOW and Java service metadata
- Exact local document-reference resolution by declared `namespace:name` full name
- Unique document-to-document dependencies with `REFERENCES_DOCUMENT`
- Unique service-to-document dependencies with `USES_DOCUMENT` and `INPUT`, `OUTPUT`, or
  `INPUT_OUTPUT` usage roles
- Cycle detection for locally resolved document-reference graphs without recursive expansion
- Deterministic document Markdown under `documents/*.md`
- Service Markdown sections for compact input/output document usage and resolved/unresolved
  document references
- Graphviz document graph under `graphs/documents.dot`
- Tests for fixture-derived document counts, field trees, reference resolution, service-document
  dependencies, specification non-misclassification, document edge findings, policy behavior,
  deterministic outputs, and regression metrics

Verification baseline:

- Analyzed FLOW Services: 24
- Call occurrences: 108
- Unique service-call dependencies: 86
- Flow maps: 265
- Mapping operations: 568
- Transformer bindings: 198
- Document Types: 7
- Document fields: 33
- Document reference occurrences: 12
- Resolved document reference occurrences: 10
- Unresolved document reference occurrences: 2
- Unique document-to-document dependencies: 5
- Service-document dependencies: 7
- Specification artifacts observed but not classified as Document Types: 8

Observed local document-to-document dependencies:

- `pgp.documents.config:PGPconfig -> pgp.documents.config:KeyConfig`
- `pgp.documents:PubKeyRegEntry -> pgp.documents:KeyRegData`
- `pgp.documents:PubKeyRegEntry -> pgp.documents:PublicKeyData`
- `pgp.documents:SecKeyRegEntry -> pgp.documents:KeyRegData`
- `pgp.documents:SecKeyRegEntry -> pgp.documents:PrivateKeyData`

Observed service-document dependencies:

- Five PGP service signature references resolve to local PGP Document Types.
- Two OAAdapter service signature references remain unresolved because the corresponding Document
  Type artifacts are not present in the analyzed snapshot.

Not implemented in M3:

- Specification IR or specification document-reference dependency modeling
- Package dependency graph extraction
- Schema-aware validation that mapping paths exist in Document Types
- Recursive document expansion
- Business descriptions or semantic enrichment
- Java service body decoding or analysis
- Adapter, trigger, scheduler, process, Ollama, snapshot diff, or Integration Server connectivity

## Next Milestone Gate

M3 hardening was explicitly approved to address accepted M3 audit issues before M4.

## M3 Hardening: Document Markdown Policies And Document Findings

Implemented in this hardening milestone:

- Document Markdown now renders the active disclosure policy snapshot on every document page:
  free-text mode, literal mode, secret-guard enabled state, and secret-guard strategy.
- `MALFORMED_NESTED_RECORD` is emitted with `WARNING` severity when nested record metadata is
  structurally malformed but safe parsing can continue. Supported conditions are non-array
  `rec_fields` metadata and non-record direct children inside a `rec_fields` array.
- Empty record fields remain allowed and do not emit `MALFORMED_NESTED_RECORD` by themselves.
- `UNSUPPORTED_DOCUMENT_METADATA` is emitted with `INFO` severity when a document or field contains
  structurally valid metadata that is preserved as policy-controlled evidence but not interpreted by
  the current IR.
- Unsupported metadata values remain filtered through the existing disclosure policy. Findings expose
  metadata names, owner type, source evidence, disclosure status, occurrence count, and bounded
  source samples without printing raw values.
- Repetitive unsupported metadata findings aggregate deterministically by metadata name, owner type,
  source file, artifact type, and disclosure status.

Verification baseline remains unchanged:

- Analyzed FLOW Services: 24
- Call occurrences: 108
- Unique service-call dependencies: 86
- Flow maps: 265
- Mapping operations: 568
- Transformer bindings: 198
- Document Types: 7
- Document fields: 33
- Document reference occurrences: 12
- Resolved document reference occurrences: 10
- Unresolved document reference occurrences: 2
- Unique document-to-document dependencies: 5
- Service-document dependencies: 7

Not implemented in M3 hardening:

- Document default/fixed-value extraction
- Specification IR
- Schema-aware mapping validation
- Java service body decoding or analysis
- Adapter, trigger, scheduler, process, Ollama, snapshot diff, or Integration Server connectivity

## Next Milestone Gate

M4a deterministic Java Service analysis was explicitly approved and implemented.

## M4a Deterministic Java Service Analysis

Implemented in this milestone:

- Analysis schema migration from `analysis.v5` to `analysis.v6`.
- Java Service records integrated as `service_type=JAVA` services while preserving the FLOW Service
  count separately.
- Source-first generated Java source association from service namespace to `code/source`.
- Matched service-method selection scoped to the generated service class.
- Token-normalized comparison between complete source method bodies and sibling `java.frag` bodies.
- Source consistency statuses:
  `SOURCE_AND_FRAGMENT_MATCH`, `SOURCE_ONLY`, `FRAGMENT_ONLY`, `SOURCE_FRAGMENT_MISMATCH`,
  `SOURCE_METHOD_NOT_FOUND`, `SOURCE_METHOD_AMBIGUOUS`, and `SOURCE_IDENTITY_MISMATCH`.
- `java.frag` fallback for missing, mismatched, ambiguous, missing-method, or identity-mismatched
  complete source.
- Java import reconciliation from complete source and `node.idf` metadata with explicit mismatch
  findings.
- Referenced-type extraction from the matched method for explicitly imported types.
- Method-scoped observed pipeline access extraction for `IDataUtil.get*`, `IDataUtil.put`, and
  `IDataUtil.remove`, including literal keys, dynamic-key findings, and cursor scopes.
- Narrow Java `Service.doInvoke` extraction for literal canonical targets, literal namespace/service
  arguments, literal `NSName` construction, and local literal variables before reassignment.
- Exact resolution of statically confirmed Java invocation targets against discovered FLOW and Java
  services.
- Java Service Markdown sections for source consistency, pipeline accesses, invocation sites,
  imports, referenced types, findings, limitations, and source evidence.
- Dependency DOT integration for statically confirmed Java invocation edges.
- Tests for source statuses, fragment fallback, mismatch fallback, method ambiguity, method
  isolation, comments/strings, helper isolation, dynamic keys, unknown cursor scope, remove,
  static/dynamic/partially static Java invocation targets, FLOW and Java target resolution,
  repeated-call aggregation, and stable deterministic output behavior.

Verification baseline:

- FLOW Services: 24.
- Java Services: 11.
- FLOW call occurrences: 108.
- FLOW-derived unique service dependencies: 86.
- Java static call occurrences: 0.
- Java unique service dependencies: 0.
- Flow maps: 265.
- Mapping operations: 568.
- Transformer bindings: 198.
- Document Types: 7.
- Document fields: 33.
- Document reference occurrences: 12.
- Unique document-to-document dependencies: 5.
- Service-document dependencies: 7.
- Java Service analyses: 11.
- Source/fragment token matches: 11.
- Java pipeline accesses: 73, split into 37 `READ`, 36 `WRITE`, and 0 `REMOVE`.
- Java access scopes: 55 `ROOT_PIPELINE` and 18 `NESTED_IDATA`.
- Java invocation occurrences in the current fixtures: 0.

Corrected Java fixture decision:

- `pgp.services.decrypt:decryptAndVerify` contains two multiline
  `IDataUtil .get(pc, "...KeyRingCollection")` calls. `pc` is assigned from `pipeline.getCursor()`,
  the complete source and `java.frag` agree token-wise, and the reads are not from a nested/local
  `IData` object. They are therefore genuine observed root pipeline reads and are counted even
  though declared signatures and observed Java accesses are separate evidence.

Not implemented in M4a:

- Broad Java external-effect classification.
- Helper-body effect analysis.
- Java compilation, execution, class loading, or runtime simulation.
- Adapter parsers, trigger parsers, schedulers, process models, package dependency graphs, snapshot
  diffing, Ollama integration, or M5 work.

## Next Milestone Gate

M4a acceptance remediation was explicitly approved after audit found method-signature authority and
nested executable-body over-extraction issues.

## M4a Acceptance Remediation

Implemented in this remediation:

- Complete-source Java Service authority now requires a direct generated-class method with the
  exact service name, `static`, `void`, and exactly one `IData` parameter. The parameter may be
  `IData` or `com.wm.data.IData`, with harmless annotations allowed.
- Same-name methods with unsupported signatures emit
  `JAVA_SOURCE_METHOD_SIGNATURE_UNSUPPORTED` and use `java.frag` fallback when available.
- Multiple compatible same-name methods emit `JAVA_SOURCE_METHOD_AMBIGUOUS` and are not selected
  arbitrarily.
- Malformed or unbalanced complete-source class/method structure emits `JAVA_SOURCE_PARTIAL_PARSE`
  and uses `java.frag` fallback when available.
- Java API-looking sites inside lambda bodies, anonymous-class methods, and local-class bodies are
  skipped as direct service evidence with bounded `JAVA_NESTED_EXECUTABLE_BODY_SKIPPED` findings.
  Normal control-flow blocks remain analyzed.
- CLI completion output now reports FLOW, Java, and total service counts; FLOW, Java static, Java
  dynamic/partial, and total promoted call counts; and FLOW-derived, Java-derived, and total unique
  dependency counts.
- Fully qualified type usages without imports remain explicitly deferred in M4a; referenced-type
  extraction covers imported types observed in the direct service method.

Expected baseline remains unchanged:

- FLOW Services: 24.
- Java Services: 11.
- FLOW call occurrences: 108.
- FLOW-derived unique service dependencies: 86.
- Java static call occurrences: 0.
- Java unique service dependencies: 0.
- Java Service analyses: 11.
- Source/fragment token matches: 11.
- Java pipeline accesses: 73, split into 37 `READ`, 36 `WRITE`, and 0 `REMOVE`.
- Java access scopes: 34 root reads, 3 nested reads, 21 root writes, and 15 nested writes.

Not implemented in M4a remediation:

- Broad Java external-effect classification.
- Helper-body effect analysis.
- Fully qualified non-imported type-reference extraction.
- Java compilation, execution, class loading, or runtime simulation.
- Adapter parsers, trigger parsers, schedulers, process models, package dependency graphs, snapshot
  diffing, Ollama integration, M4b, or M5 work.

## Next Milestone Gate

M5-lite opaque service inventory was explicitly approved after representative JDBC Adapter Service
fixtures were found to be unavailable.

## M5-lite Opaque Service Inventory

Implemented in this milestone:

- Analysis schema migration from `analysis.v6` to `analysis.v7`.
- Generic discovery of parseable service-like `node.ndf` artifacts with an explicit top-level
  unsupported `svc_type` as `service_type=OPAQUE` after surrounding whitespace is trimmed. Missing,
  empty, whitespace-only, malformed, or non-scalar service-type metadata remains inventory-only.
- Common metadata extraction for opaque services: namespace-path identity, trimmed source service
  type, top-level `node_comment` under the existing free-text policy, `svc_sig` signatures, source
  evidence, and bounded findings.
- Service support statuses: `FULL`, `PARTIAL`, and `OPAQUE`.
- Exact dependency resolution to opaque services when FLOW or Java call evidence names the opaque
  service by canonical full name.
- Service-only dependency DOT behavior retained; opaque services appear as service nodes, while no
  database, messaging, scheduler, trigger, process, or external-resource nodes are introduced.
- CLI, JSON, and Markdown output for service kind counts, support status, description status,
  opaque services, and resolved opaque targets.
- Deterministic service Markdown `Called By` sections derived from resolved static dependency
  evidence.
- Disclosure-safe malformed XML findings: parser diagnostics are sanitized before serialization,
  relative `SourceReference.path` remains authoritative, and malformed XML findings omit
  `source_node` when no XML structure is available.
- Malformed common service descriptions report the actual `node_comment` Values child shape.
- Synthetic tests for opaque service discovery, exact dependency resolution, disclosure policies,
  malformed common metadata, secret safety, whitespace-only false positives, Java-to-opaque calls,
  CLI metrics, incoming-call Markdown, and deterministic IDs.

Verification baseline:

- Current real fixtures contain 24 FLOW Services, 11 Java Services, and 0 opaque services.
- All current fixture services are fully analyzed by supported FLOW or Java parsers.
- Existing M4a FLOW, Java, mapping, document, dependency, Markdown, DOT, and fixture checksum
  behavior remains stable apart from the schema and new zero-valued opaque metrics.

Not implemented in M5-lite:

- Detailed JDBC Adapter Service parsing.
- SQL, table, view, stored-procedure, connection-alias, or database-resource extraction.
- UM/JMS destination extraction, trigger semantics, scheduler cadence, process models, M4b Java
  external-effect analysis, runtime execution, Integration Server connectivity, database
  connectivity, Ollama, snapshot diffing, SVG/PNG rendering, or M6 work.

## Next Milestone Gate

M5-lite should receive a final acceptance re-audit after this remediation before any broader
milestone planning.

M4b, detailed JDBC/M5, M6, or any later milestone requires explicit approval before implementation.
