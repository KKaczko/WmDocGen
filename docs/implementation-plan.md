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

M3 must start only after explicit approval. Recommended M3 scope remains document types,
specifications, `rec_ref` usage, and package graph extraction from observed fixtures.
