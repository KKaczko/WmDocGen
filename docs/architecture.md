# Architecture

M5-lite implements package/artifact inventory plus FLOW Service, Document Type, Java Service, and
opaque service static-analysis slices focused on traceable calls, unique dependencies, observed
control-flow structure, observed mapping evidence, ordered document field trees, exact
document-reference resolution, source-first Java Service evidence, opaque service identity, and
policy-safe disclosure.

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
  extraction policies, and typed findings.
- Renderers produce deterministic inventory JSON/Markdown and deterministic analysis JSON,
  per-service Markdown, per-document Markdown, and Graphviz DOT.
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

The M2b FLOW parser remains feature-based. It interprets only observed structures needed for this
milestone and records other observed uppercase FLOW or mapping elements as findings instead of
treating them as silently supported. Mapping paths preserve the raw declared webMethods path as
authoritative; derived `PipelinePath` fields are lightweight flags, not schema resolution.

M3 document parsing is also feature-based. It maps only observed field types (`string`, `object`,
`record`, `recref`) and observed dimensions (`0`, `1`). It does not validate mapping paths against
document schemas, recursively expand referenced documents, interpret field names as business
semantics, or model Specification artifacts as Document Types.

Later milestones may add broad Java external-effect classification, fuller FLOW semantics, detailed
adapter fixtures, JDBC/database resources, trigger fixtures, scheduler fixtures, process graphs,
Service Specification IR, package dependency graphs, snapshot diffing, and Ollama input generation.
Those are intentionally outside M5-lite and require a separate gate.
