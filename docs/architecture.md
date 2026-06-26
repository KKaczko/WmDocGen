# Architecture

M8a implements package/artifact inventory plus FLOW Service, Document Type, Java Service, opaque
service, and user-maintained process static-analysis slices focused on traceable calls, unique
dependencies, observed control-flow structure, observed mapping evidence, ordered document field
trees, exact document-reference resolution, source-first Java Service evidence, opaque service
identity, optional `processes.yml` catalogs, policy-safe disclosure, and optional derived graph
publishing for Markdown-oriented repository viewers. It also adds focused publication scopes that
limit generated Markdown and focused graph output after the complete M7 analysis result is built.

Subsystems:

- Discovery locates package roots, namespace folders, and artifact file combinations.
- Secure XML parsing lives in `wm_doc.xmlsafe` and rejects DTD/entity declarations.
  XML parser diagnostics are sanitized at this boundary so canonical findings keep relative
  `SourceReference.path` as the authoritative location without repeating absolute local paths in
  messages.
- `Values` parsing extracts safe metadata from `manifest.v3`, `node.idf`, and `node.ndf`.
- Service analysis in `wm_doc.analysis` parses observed FLOW Service signatures, `flow.xml`
  structures, Java Service metadata, and common opaque service metadata without executing package
  code.
- Java Service analysis in `wm_doc.java_analysis` associates services with generated source under
  `code/source`, selects only the matched service method, compares it with `java.frag` using
  normalized Java tokens, and extracts method-scoped Java evidence.
- Opaque Service analysis retains parseable service-like `node.ndf` artifacts with explicit
  unsupported trimmed `svc_type` values as service identities, but interprets only common metadata:
  identity, source service type, safe `node_comment`, signatures, source evidence, and findings.
  Missing, empty, whitespace-only, malformed, or non-scalar service-type metadata is not promoted to
  an opaque service.
- Process catalog analysis in `wm_doc.process_catalog` and `wm_doc.process_analysis` parses an
  optional safe `processes.yml`, validates exact canonical entrypoints, traverses resolved local
  service dependencies with deterministic BFS, retains unresolved calls from member services, derives
  process/document relationships, and emits technical entrypoint candidates for services with zero
  incoming resolved local dependencies.
- Graph publishing in `wm_doc.graph_publish` discovers the DOT paths produced by the renderers and,
  only when requested, invokes Graphviz `dot` with argument-list subprocess calls to create derived
  SVG/PNG files. Render failures do not change canonical analysis or DOT output.
- Focused publication in `wm_doc.scope_analysis` consumes the complete `AnalysisResult`, resolves
  exactly one CLI selector, traverses resolved `UniqueDependency` records with deterministic BFS,
  records bounded provenance, extracts scope boundaries from resolved depth limits, unresolved
  static dependencies, dynamic invocation evidence, and unsupported call-like findings, computes
  document closure from canonical service/document relationships, and writes `scope.v1` separately
  from canonical analysis.
- Classification in `wm_doc.config` applies deterministic, case-insensitive glob rules. `neverImportant`
  rules take precedence over important service rules.
- Dependency resolution is exact-name only. It resolves static `INVOKE`, `MAPINVOKE`, and
  statically confirmed Java invocation targets to discovered FLOW, Java, or opaque Service metadata
  and keeps unresolved targets explicit in the IR.
- Document Type analysis parses observed `record/node_type=record` metadata into ordered field
  trees. It resolves `rec_ref` values only by exact local `namespace:name` match and keeps unresolved
  targets explicit.
- IR models in `wm_doc.ir` preserve source references, confidence basis, finding statuses,
  classifications, call occurrences, unique dependencies, an ordered FLOW tree, flow maps, typed
  mapping operations, transformer bindings, document types, document-reference occurrences,
  document dependencies, service-document dependencies, Java source sets, Java imports, Java type
  references, Java pipeline accesses, Java invocation occurrences, service support statuses,
  process definitions, process entrypoint validation, process memberships, process dependency edges,
  process unresolved calls, process document relationships, technical entrypoint candidates,
  extraction policies, and typed findings.
- Renderers produce deterministic inventory JSON/Markdown and deterministic analysis JSON,
  top-level index Markdown, entrypoint candidate Markdown, per-service Markdown, per-document
  Markdown, process Markdown, graph catalog Markdown, Graphviz DOT, and optional derived SVG/PNG
  graph assets.
- The CLI exposes `wm-doc scan` and `wm-doc analyze`.

## Analysis Schema

`analysis.v1` used `edges` for concrete call sites. M2a migrated to `analysis.v2`:

- `call_occurrences` stores each concrete static `INVOKE` or `MAPINVOKE` site with source evidence,
  structural path, parent FLOW path, call type, dependency kind, and resolved status.
- `unique_dependencies` aggregates repeated calls by `(caller, target, dependency kind)` and retains
  occurrence counts plus deterministic occurrence IDs.
- `INVOKE` maps to dependency kind `INVOKES`.
- `MAPINVOKE` maps to dependency kind `USES_TRANSFORMER`.
- `flow_tree` stores ordered FLOW nodes for `FLOW`, `SEQUENCE`, `BRANCH`, derived `BRANCH_CASE`,
  `LOOP`, structural `MAP`, `INVOKE`, `MAPINVOKE`, and `EXIT`.
- `EXIT` nodes preserve observed `FROM`, `SIGNAL`, and `FAILURE-MESSAGE` attributes. Unknown EXIT
  shapes are still parsed and also produce findings.

M2b migrates to `analysis.v3`:

- `flow_maps` stores observed `MAP` containers with stable IDs, structural paths, `MODE`, parent
  call references, raw attributes, source evidence, and attached `MAPSOURCE`/`MAPTARGET` metadata
  summaries.
- `mapping_operations` stores typed `COPY`, `SET`, and `DELETE` operations derived from observed
  `MAPCOPY`, `MAPSET`, and `MAPDELETE` elements.
- `transformer_bindings` stores evidence-only bindings for `MAPINVOKE` child maps with
  `MODE="INVOKEINPUT"` or `MODE="INVOKEOUTPUT"`.
- `extraction_policy` records the active literal and free-text disclosure modes that shaped the
  output.
- Call occurrence IDs, flow map IDs, mapping operation IDs, and binding IDs use deterministic
  SHA-derived prefixes.

M2b remediation migrates to `analysis.v4`:

- Policy-controlled text is stored as structured text metadata instead of raw strings.
- Free-text policy applies before canonical serialization to service descriptions, FLOW labels,
  free-text `NAME` attributes, display labels, and mapping operation names.
- Structural and technical values remain raw when needed for static analysis, including service
  targets, pipeline paths, branch switches, loop arrays, exit attributes, and mapping endpoints.
- Raw attribute collections are filtered to technical values only. Free-text attributes are stored
  as policy-safe text metadata, and unknown attributes preserve name/source/presence without raw
  values unless explicitly classified as technical.
- The extraction policy snapshot records the active modes and the deterministic secret guard
  strategy.
- Mapping operations keep service-local discovery order and additionally expose per-map direct-child
  order plus document traversal order. These are evidence orderings, not runtime execution order.

M3 migrates to `analysis.v5`:

- `document_types` stores local Document Type artifacts with package/name identity, source
  references, policy-safe descriptions, and ordered `DocumentField` trees.
- `DocumentField` preserves raw field type, canonical field type, raw dimension, interpreted
  dimension, source order, structural path, display field path, technical metadata, policy-safe text
  metadata, unknown metadata, and ordered children.
- `document_reference_occurrences` stores every observed document reference from Document Type fields
  and service signatures, preserving the declared target and exact local resolution status.
- `document_dependencies` aggregates document-to-document `REFERENCES_DOCUMENT` occurrences.
- `service_document_dependencies` aggregates service signature document usage with `INPUT`,
  `OUTPUT`, or `INPUT_OUTPUT` roles.
- `graphs/documents.dot` renders unique document-to-document edges and unresolved target nodes. The
  service-call graph remains separate in `graphs/dependencies.dot`.

M3 hardening keeps `analysis.v5` and adds two traceability improvements:

- Document Markdown receives the active `extraction_policy` snapshot from canonical analysis IR and
  renders free-text mode, literal mode, secret-guard enabled state, and secret-guard strategy on
  every document page.
- `MALFORMED_NESTED_RECORD` is emitted with `WARNING` severity when nested document record metadata
  is demonstrably malformed but the field can still be represented safely. Current conditions are a
  non-array `rec_fields` metadata container or non-record child elements inside a `rec_fields` array.
- `UNSUPPORTED_DOCUMENT_METADATA` is emitted with `INFO` severity when structurally valid document
  or field metadata is preserved as policy-controlled evidence but not interpreted by the current
  canonical model. Values remain filtered by the disclosure policy.
- Repeated unsupported metadata findings aggregate deterministically by metadata name, owner type,
  file, and disclosure status, with bounded source samples preserving field paths.

M4a migrates to `analysis.v6`:

- Java Services are emitted as services with `service_type=JAVA` and companion
  `java_service_analyses` records at package and top level.
- `JavaSourceSet` records `node.ndf`, optional complete source, optional `java.frag`,
  related helper source inventory, matched class/method, method range, parser mode, token-match
  state, and one of these statuses: `SOURCE_AND_FRAGMENT_MATCH`, `SOURCE_ONLY`, `FRAGMENT_ONLY`,
  `SOURCE_FRAGMENT_MISMATCH`, `SOURCE_METHOD_NOT_FOUND`, `SOURCE_METHOD_AMBIGUOUS`, or
  `SOURCE_IDENTITY_MISMATCH`, plus `SOURCE_PARTIAL_PARSE` for malformed complete-source structure.
- Complete source is the preferred parsing surface only when identity and method matching are
  reliable. A compatible generated Java Service method must be a direct method of the verified
  generated class, have the exact service name, be `static`, return `void`, and accept exactly one
  `IData` parameter (`IData` or `com.wm.data.IData`, with harmless annotations allowed). `java.frag`
  is corroborating evidence for matches and the fallback parsing surface when source is missing,
  mismatched, ambiguous, malformed, identity-inconsistent, or contains only unsupported same-name
  method signatures.
- The Java scanner removes comments and treats string, character, and text-block literals as
  literals, so fake API calls inside comments or arbitrary strings do not create pipeline accesses
  or invocation occurrences.
- Java evidence is promoted only from the direct service-method executable body. Normal control
  blocks remain in scope, but lambda bodies, anonymous-class methods, and local-class bodies are
  skipped with bounded `JAVA_NESTED_EXECUTABLE_BODY_SKIPPED` findings because M4a does not model
  callback/control-flow execution for nested executable code.
- Malformed complete-source class or method structure emits `JAVA_SOURCE_PARTIAL_PARSE`; the
  analyzer does not use method-not-found as the only diagnosis for structurally unsafe source.
- Observed Java pipeline accesses record `READ`, `WRITE`, or `REMOVE`, literal field keys when
  statically present, dynamic-key findings otherwise, and cursor scope as `ROOT_PIPELINE`,
  `NESTED_IDATA`, or `UNKNOWN_CURSOR`. Declared service signatures are separate evidence and do not
  suppress observed Java behavior.
- Java imports and referenced types are evidence, not service dependencies. Import provenance can be
  complete source, `node.idf`, or both; mismatches are explicit findings. M4a referenced-type
  extraction covers imported types observed in the direct service method and intentionally does not
  claim coverage for non-imported fully qualified type expressions.
- Only narrowly supported static `Service.doInvoke` targets become `JAVA_INVOKE` call occurrences,
  unique dependencies, and `graphs/dependencies.dot` edges. Dynamic and partially static targets
  remain Java invocation evidence/findings and do not create guessed dependency nodes.
- Java disclosure excludes complete Java bodies, decoded `java.frag` bodies, raw token streams,
  arbitrary Java literals, absolute local paths, and wrapper-only source coordinates.

M5-lite migrates to `analysis.v7`:

- Services carry `source_service_type`, `analysis_status`, and `description_status`.
- `service_type=OPAQUE` represents parseable service artifacts whose top-level `svc_type` is
  explicit after whitespace trimming but not a supported FLOW, Java, or Specification type.
- Opaque services are normal services for exact incoming call resolution and
  `graphs/dependencies.dot` nodes, but no implementation-derived outgoing calls or external
  resources are inferred from them.
- `ServiceSummary`, call occurrences, and unique dependencies preserve target analysis support
  status so callers can distinguish fully analyzed, partial, and opaque targets.
- Service Markdown renders an `Analysis Support` section for all services and a deterministic
  `Called By` section from resolved static FLOW/Java dependency evidence.
- Metrics include service kind counts, support-status counts, description-status counts, opaque
  service counts, and resolved target-type counts.
- M5-lite does not add JDBC, SQL, database-resource, connection-alias, UM/JMS, trigger, scheduler,
  process, or M4b Java effect models. Those remain fixture-gated future milestones.

M6 migrates to `analysis.v8`:

- `processes.yml` version 1 is optional. When omitted, `<scan-root>/processes.yml` is auto-detected;
  default absence is normal and not a finding. An explicit missing path emits
  `PROCESS_CONFIG_MISSING` but analysis continues.
- Process catalog parsing uses PyYAML safe loading with duplicate-key, alias/anchor, custom-tag,
  multi-document, size, process-count, and entrypoint-count guards. Raw YAML and unknown property
  values are never serialized.
- Process definitions are top-level records because a process can span packages. User IDs use the
  safe regex `[a-z0-9][a-z0-9._-]{0,127}` and become `processes/<id>.md` and
  `graphs/processes/<id>.dot` filenames without rewriting.
- Declared entrypoints are exact canonical service full names. Statuses are `RESOLVED`, `NOT_FOUND`,
  `DUPLICATE`, and `AMBIGUOUS`; no short-name, fuzzy, package-prefix, or similarly named fallback is
  attempted. Process Markdown keeps the user-authored `Declared Entrypoints` table separate from
  `Entrypoint Validation`, which shows the static resolution status and links only resolved service
  pages.
- Process membership is deterministic BFS over resolved `UniqueDependency` records with
  `INVOKES` and `USES_TRANSFORMER` kinds. Memberships retain minimum depth, entrypoint flags,
  reached-from entrypoint IDs, and shortest representative dependency-ID paths.
- Process edges reference existing unique service dependencies. Unresolved dependencies from member
  services become process unresolved call facts rather than inferred services or external systems.
- Process document relationships are derived from existing service/document and document/document
  dependency evidence using neutral roles such as `SERVICE_INPUT`, `ENTRYPOINT_OUTPUT`, and
  `DOCUMENT_DEPENDENCY`. Process Markdown links a relationship only when it is resolved and the
  canonical document page exists in the generated output; unresolved or inconsistent targets remain
  visible as unlinked technical identifiers.
- Technical entrypoint candidates are generated for analyzed services with zero incoming resolved
  local unique service dependencies. They are labeled as technical candidates only and never create
  business process definitions.
- M6 adds a top-level documentation index, process catalog/page Markdown, service/document process
  cross-links, `entrypoints.md`, and per-process DOT graphs. Generated Markdown link integrity is
  covered by regression tests. It does not add process-to-process overview semantics.

M7 keeps `analysis.v8`:

- DOT files remain canonical graph outputs: `graphs/dependencies.dot`, `graphs/documents.dot`, and
  `graphs/processes/<process-id>.dot` for declared processes.
- `wm-doc analyze --render-graphs none|svg|png|both` controls optional derived graph publishing.
  The default is `none`, so Graphviz is not required for normal analysis.
- The CLI resolves Graphviz `dot` from `PATH` or `--graphviz-dot`, probes it with bounded
  execution, renders each graph/format through `shell=False` subprocess calls, rejects empty output,
  validates image structure, cleans temporary files, atomically replaces completed assets, and
  reports path-scrubbed, secret-redacted diagnostics.
- Temporary-file cleanup failures are surfaced as graph-render failures or secondary failure
  details; they are not silently discarded. Cleanup diagnostics use the same path and secret
  redaction as Graphviz process diagnostics.
- SVG publishing parses Graphviz output as XML, removes the known external SVG 1.1 DTD declaration
  and comments, and rejects malformed roots, XML entities, unsafe elements, event-handler
  attributes, unsafe URI references, and absolute local paths. PNG publishing validates PNG
  signature/chunks, IHDR dimensions, IDAT presence, IEND termination, and CRCs.
- `graphs/index.md` lists every generated graph with its DOT link and only the SVG/PNG links that
  were successfully rendered. The top-level index links the graph catalog, and process pages preview
  SVG when available or PNG otherwise.
- Before publishing, the CLI removes only managed generated locations under the output root:
  `analysis.json`, `index.md`, `entrypoints.md`, `scope.json`, `scope.md`, `services`,
  `documents`, `processes`, and `graphs`. File/directory shape conflicts at those exact paths are
  replaced, unrelated files are preserved, and symlinks at managed paths are unlinked rather than
  followed.
- Rendered image files are publishing artifacts only. Their determinism depends on using the same
  Graphviz executable/version; they do not affect IR, metrics, dependency resolution, or schema.

M8a keeps `analysis.v8` and adds `scope.v1` for focused publication:

- Scope selection happens after full package discovery, parsing, dependency resolution, process
  analysis, classification, and global metrics are complete. Focused publication reduces generated
  documentation and graph scope; it does not reduce initial parsing or analysis cost.
- The full canonical `analysis.json` remains unchanged and describes the complete discovered
  snapshot. `scope.json` describes the selected publication subset. Markdown and focused graphs
  describe the selected publication subset.
- M8a v1 accepts exactly one selector occurrence per run: `--target-service`, `--target-namespace`,
  `--target-package`, or `--target-process`. `--target-namespace` uses case-sensitive namespace
  segment-boundary prefix matching, not filesystem paths.
- Root resolution uses multimaps and rejects ambiguous duplicate canonical service names, duplicate
  selected package identities, and duplicate selected process IDs instead of selecting by discovery
  order.
- Traversal follows resolved unique service dependencies only, preserving existing dependency kinds
  such as `INVOKES` and `USES_TRANSFORMER`. Dynamic, unresolved, unsupported, and depth-limited
  calls become scope boundaries.
- Scoped document pages are seeded from canonical `service_document_dependencies` for included
  services and, for process scopes, selected `process_document_relationships`, then expanded through
  deterministic document dependency closure.
- Focused output uses focused graph names such as `graphs/scope.dot` and
  `graphs/scope-documents.dot`. It does not write global `graphs/dependencies.dot` or
  `graphs/documents.dot` in scoped mode. No-selector mode remains the accepted M7 publication path.

M8b keeps `analysis.v8` and `scope.v1` unchanged and adds a separate deterministic context package:

- `wm-doc build-business-context` consumes generated focused artifacts rather than reparsing package
  snapshots. It accepts either `--input <focused-output-dir>` or explicit `--analysis` and
  `--scope` paths.
- The command validates supported schemas and cross-references before writing output. Invalid or
  incompatible inputs fail without emitting a context bundle.
- `business-context/context.json` uses schema `business-context.v1`; `business-context/context.md`
  is a deterministic human review preview, not model-authored business documentation.
- The context pack separates canonical technical facts, approved process metadata, deterministic
  summaries, boundaries, unknowns, limitations, omissions, and evidence records. Evidence IDs refer
  to stable canonical or context-specific identifiers and never to Markdown filenames or absolute
  paths.
- M8b is allowlist-based: it does not serialize raw XML, Java bodies, MAP literal values, arbitrary
  constants, absolute local paths, Graphviz diagnostics, provider settings, prompts, model
  responses, or cache metadata.
- `COMPLETE` and `PARTIAL` describe the deterministic context package. Built-in `pub.*`/`wm.*`
  boundaries are retained as limitations but do not make a context partial by themselves.

The M2b FLOW parser remains feature-based. It interprets only observed structures needed for this
milestone and records other observed uppercase FLOW or mapping elements as findings instead of
treating them as silently supported. Mapping paths preserve the raw declared webMethods path as
authoritative; derived `PipelinePath` fields are lightweight flags, not schema resolution.

M3 document parsing is also feature-based. It maps only observed field types (`string`, `object`,
`record`, `recref`) and observed dimensions (`0`, `1`). It does not validate mapping paths against
document schemas, recursively expand referenced documents, interpret field names as business
semantics, or model Specification artifacts as Document Types.

Later milestones may add broad Java external-effect classification, fuller FLOW semantics, detailed
adapter fixtures, JDBC/database resources, trigger fixtures, scheduler fixtures, native BPM
process-model parsing, Service Specification IR, package dependency graphs, snapshot diffing, and
Ollama/model-generated business documentation. Those are intentionally outside M8b and require a
separate gate.
