# Newly Observed Format Behavior

Observed from current fixtures:

- Package roots can be reconstructed from directories containing `ns/` or `manifest.v3`.
- Namespace folders use `node.idf` with `node_type=interface`.
- FLOW Services use `node.ndf` with `svc_type=flow` and usually have sibling `flow.xml`.
- Java Services use `node.ndf` with `svc_type=java` and sibling `java.frag`.
- Java Service generated source is stored under `code/source` using the namespace class path, such
  as `pgp.services.decrypt:decryptAndVerify` mapping to
  `PGP/code/source/pgp/services/decrypt.java`.
- Specifications use `node.ndf` with `svc_type=spec`.
- M5-lite trims surrounding whitespace before interpreting top-level `svc_type`. A parseable
  service-like `node.ndf` with a non-empty trimmed `svc_type` other than `flow`, `java`, or `spec`
  becomes an opaque service. Identity comes from the namespace path, the trimmed source service type
  is preserved, and only common metadata is parsed.
- A missing, empty, or whitespace-only top-level `svc_type` is not enough to promote an arbitrary
  `node.ndf` directory to a service. Such artifacts remain inventory-only unknowns unless another
  fixture-proven rule applies.
- M6 process catalogs are user-maintained YAML files named `processes.yml` by default or supplied
  with `--processes-file`. The supported shape is `version: 1` plus a `processes` list containing
  stable safe IDs, scalar names, optional scalar descriptions, and exact canonical service full-name
  entrypoints.
- Process descriptions are user-authored free text and are filtered by the same free-text policy and
  secret guard as service/document descriptions. Process IDs and names are structural catalog
  metadata and remain visible.
- Process catalog parsing rejects duplicate YAML keys, aliases/anchors, custom tags, multiple
  documents, oversized files, unsafe IDs, malformed names, malformed descriptions, malformed
  entrypoints, duplicate process IDs, and over-limit catalogs with explicit findings. Raw YAML and
  unknown YAML property values are not serialized.
- Declared process entrypoints are exact only. The analyzer records `RESOLVED`, `NOT_FOUND`,
  `DUPLICATE`, or `AMBIGUOUS`; it does not do short-name matching, namespace guessing, fuzzy
  matching, or similarly named fallback. Per-process Markdown keeps declared catalog values and
  entrypoint validation in separate sections so user-authored declarations are not confused with
  analyzer-confirmed resolution.
- Process traversal uses resolved local unique service dependencies with `INVOKES` and
  `USES_TRANSFORMER` kinds. Opaque services can be members but are terminal unless future canonical
  outgoing dependency evidence exists.
- Process document relationship Markdown links only resolved canonical documents whose generated
  document pages exist. Unresolved document targets remain visible as code-form technical
  identifiers marked `UNRESOLVED`; inconsistent resolved-but-missing targets are also rendered
  without links rather than producing broken output.
- Technical entrypoint candidates are services with zero incoming resolved local unique service
  dependencies. They are reported as technical root candidates, not confirmed business entrypoints.
- Generated Markdown link integrity is regression-tested for no-catalog, fixture-catalog,
  synthetic unresolved-document, graph-image, stale-output, and free-text include/redact/omit
  outputs.
- M7 graph publishing always treats DOT as canonical. `graphs/index.md` is generated for every
  analysis and lists each DOT graph plus SVG/PNG links only when those derived files exist.
- `--render-graphs none` is the default. `svg`, `png`, and `both` request Graphviz rendering for
  every current DOT graph, including per-process DOT files. Graphviz is resolved from `PATH` unless
  `--graphviz-dot` is supplied.
- Rendered SVG/PNG files are derived publishing artifacts. Failed rendering leaves analysis JSON,
  Markdown, and DOT files available, omits failed image links, reports bounded safe diagnostics, and
  returns a non-zero CLI status when rendering was explicitly requested.
- Graphviz, temporary-file, and generated-output cleanup diagnostics are scrubbed before CLI
  disclosure. Absolute paths are replaced, JDBC-like connection strings are redacted, and
  secret-like key/value forms such as `password=`, `passwd=`, `access_token=`, `api-key:`, and
  bearer authorization values do not expose their values. Raw renderer stderr/stdout is not written
  to canonical JSON, Markdown, graph indexes, or process/service/document pages.
- Generated-output cleanup is shape-tolerant only for managed generated paths:
  `analysis.json`, `index.md`, `entrypoints.md`, `services`, `documents`, `processes`, and
  `graphs`. Other output-root files are outside the managed cleanup contract.
- SVG output is accepted only after XML parsing and normalization. The known Graphviz SVG 1.1
  external DTD declaration and comments are removed; malformed XML, entity declarations, script,
  JavaScript URLs, `foreignObject`, event handlers, `file://` links, absolute local paths, and
  unexpected external hrefs are rejected. PNG output must be structurally valid PNG data with valid
  chunk CRCs, non-zero IHDR dimensions, IDAT data, and a final IEND chunk.
- Document types can appear as `node.ndf` with a top-level `record` containing
  `node_type=record`.
- Observed active Document Types in current fixtures all come from PGP. OAAdapter contains service
  signature `rec_ref` values but no local Document Type artifacts in the included snapshot.
- Observed Document Type identities use `record/node_nsName` in exact `namespace:name` form. The
  analyzer keeps the directory-derived identity as fallback evidence and reports mismatches instead
  of aliasing names.
- Observed Document Type metadata includes `node_pkg`, `node_comment`, `node_hints`,
  `wrapper_type`, `nillable`, `form_qualified`, `is_global`, `is_public`, `modifiable`,
  `rec_closed`, `field_content_type`, `is_soap_array_encoding_used`, and `field_options`.
- Observed document field types are `string`, `object`, `record`, and `recref`. These map to
  canonical `STRING`, `OBJECT`, `RECORD`, and `DOCUMENT_REFERENCE`; any other type is reported as
  `UNKNOWN_FIELD_TYPE`.
- Observed document dimensions are raw `0` and `1`, interpreted as `SCALAR` and `LIST`. Missing,
  invalid, or unsupported dimensions are explicit findings.
- Nested document records are preserved as ordered field trees. Readable `field_path` values such as
  `keys/keys` are derived only for display; structural paths use source-order indexes.
- Empty nested record containers are accepted. `MALFORMED_NESTED_RECORD` is emitted only when
  nested-record metadata is structurally incompatible with observed Values shape: a `rec_fields`
  metadata child exists but is not an array, or a `rec_fields` array contains direct children that
  are not record elements. Parsing continues and valid sibling fields remain available.
- Observed `recref` document fields use exact `rec_ref` full names. Resolution is local exact-match
  only; the analyzer does not do alias, fuzzy, package-prefix, or runtime resolution.
- Metadata names in the document allowlist are treated as supported technical or policy-controlled
  metadata. Other structurally valid named metadata emits `UNSUPPORTED_DOCUMENT_METADATA`; the
  metadata name and source remain visible, while values are represented through the existing
  disclosure policy and are not interpreted semantically.
- Specification artifacts can also contain service-signature-style `rec_ref` values, but M3 does not
  classify specifications as Document Types or model a Specification IR.
- FLOW roots observed in active fixtures use `<FLOW VERSION="3.0" CLEANUP="true">`.
- Observed FLOW Services carry signatures in `node.ndf` under `svc_sig/sig_in/sig_out`.
- Observed signature fields can carry `field_name`, `field_type`, `field_dim`, `field_opt`,
  `wrapper_type`, nested `rec_fields`, and document references in `rec_ref`.
- Opaque services reuse the same common `svc_sig` structure when present. Malformed common
  signature shapes are reported as `SERVICE_SIGNATURE_METADATA_PARTIAL`; no adapter-specific
  signature, SQL, connection, table, trigger, or scheduler metadata is interpreted.
- Signature source evidence points to the actual observed `svc_sig` metadata shape. A malformed
  scalar or array `svc_sig` is reported against `/Values/value[@name='svc_sig']` or
  `/Values/array[@name='svc_sig']`, not rewritten as if a record had been present.
- Top-level `node_comment` is the only common service description field currently extracted for
  FLOW, Java, and opaque services. It is filtered by the free-text disclosure policy before
  serialization. Non-scalar `node_comment` values emit `SERVICE_DESCRIPTION_MALFORMED`.
  Malformed-description findings point to the actual observed Values child shape, such as
  `/Values/record[@name='node_comment']` or `/Values/array[@name='node_comment']`, instead of
  inventing a scalar value path.
- Malformed XML findings preserve a safe parser reason and use relative `SourceReference.path` for
  file location. When XML structure is unavailable, `source_node` is omitted.
- Observed Java Service `node.ndf` files may omit local `svc_sig` records while naming a
  Specification with `svc_spec`. M4a keeps declared signatures and observed Java pipeline accesses
  separate and does not require a Java access key to appear in the declared signature.
- Observed static service calls use `INVOKE` or `MAPINVOKE` with a `SERVICE` attribute.
- M2a treats `INVOKE` as a normal service call and `MAPINVOKE` as a transformer call. M2b adds
  evidence-only transformer binding extraction for observed `MAPINVOKE` child maps.
- Observed container-like FLOW elements include `FLOW`, `SEQUENCE`, `BRANCH`, `LOOP`, and structural
  `MAP`.
- `SEQUENCE` elements can carry `NAME`, `EXIT-ON`, `FORM`, and `TIMEOUT`. `FORM` is preserved as raw
  evidence and is not interpreted as try/catch/finally behavior.
- `BRANCH` elements can carry `SWITCH`, `LABELEXPRESSIONS`, and `TIMEOUT`. Direct child `NAME`
  labels are preserved as ordered `BRANCH_CASE` nodes; `$default` is marked only when directly
  observed.
- `LOOP` elements can carry `NAME`, `IN-ARRAY`, optional `OUT-ARRAY`, and `TIMEOUT`. M2a does not
  simulate iterations or infer collection schemas.
- OAAdapter 10.15 has 9 observed `EXIT` elements. All observed active fixture exits carry `FROM`,
  `SIGNAL="SUCCESS"`, and an empty `FAILURE-MESSAGE`.
- OAAdapter 10.15 uses `LOOP` and `EXIT`; PGP active FLOW fixtures do not currently show either tag.
- Observed `MAP`-family elements can contain nested operations and invocations. M2b positions
  structural `MAP` nodes in the FLOW tree and also extracts canonical mapping records for observed
  `MAPCOPY`, `MAPSET`, `MAPDELETE`, `MAPSOURCE`, `MAPTARGET`, and `DATA`.
- Observed `MAPSOURCE` and `MAPTARGET` elements are direct children of `MAP`, paired in the current
  active fixtures, and are treated as map-level pipeline/schema metadata summaries.
- Observed `MAPCOPY` elements use `FROM` and `TO` attributes as declared endpoints. Optional
  `NAME` and other free-text-like attributes are represented with the policy-aware text model and
  are not preserved verbatim in raw attributes.
- Observed `MAPSET` elements use `FIELD` as the target endpoint and a child `DATA` payload. Literal
  values default to redacted output; type/name/length metadata is kept when safely available.
- Observed `MAPDELETE` elements use `FIELD` as the deleted endpoint. Optional `NAME` and other
  free-text-like attributes are represented with the policy-aware text model and are not preserved
  verbatim in raw attributes.
- Observed `DATA` payloads under active fixture `MAPSET` elements use `ENCODING="XMLValues"` and
  `I18N="true"`. The parser extracts scalar literal evidence only according to the configured
  disclosure policy.
- Observed `MAPINVOKE` child maps use `MODE="INVOKEINPUT"` and `MODE="INVOKEOUTPUT"` in current
  fixtures. For `INVOKEINPUT`, `MAPCOPY FROM` is treated as the pipeline endpoint and `TO` as the
  transformer parameter endpoint. For `INVOKEOUTPUT`, `FROM` is the transformer output endpoint and
  `TO` is the pipeline endpoint.
- Pipeline paths are not schema-resolved or normalized. The raw declared path remains authoritative;
  derived path fields only record simple features such as absolute form, indexes, wildcards, and
  document-reference markers.
- Free-text-like attributes such as `NAME`, display labels, descriptions, comments if extracted, and
  mapping operation names are policy-controlled before canonical serialization. Technical
  attributes such as `SERVICE`, mapping endpoints, branch switches, loop arrays, and exit attributes
  remain available as static evidence.
- Unknown attributes are not exposed as complete raw dictionaries. The analyzer preserves attribute
  name/source/presence and policy metadata, but not raw unknown values unless a later milestone
  explicitly classifies them as technical evidence. Unknown attribute names may remain visible for
  diagnostics while their values are filtered according to the active policy.
- `flow.xml.bak` files appear beside active FLOW files and are reported as helper backups.
- PGP contains package-name evidence that differs from the directory name: `.project` reports
  `WxPGP`, and document metadata includes `node_pkg` values such as `GCS_PGP` and `WxPGP`.
- M3 adds document Markdown and document DOT rendering. These outputs include technical identifiers,
  field paths, dimensions, and resolved/unresolved reference evidence, but not raw XML, Java bodies,
  key material, defaults, or business descriptions.
- M3 hardening adds a disclosure-policy section to every document Markdown page. The values come
  from the canonical analysis policy snapshot and do not include local config paths.
- M4a adds source-first Java Service analysis. In the current fixtures all 11 Java Services match
  their complete source methods and `java.frag` bodies after token normalization. The complete source
  method is the primary parsing surface for those services.
- Java comments, block comments, Javadocs, strings, character literals, and text blocks are
  tokenized so embedded fake API calls are ignored. Balanced braces and parentheses define class and
  method ranges; ambiguous, missing, mismatched, or identity-inconsistent source falls back to
  `java.frag` when available.
- A complete-source service method is authoritative only when it is a direct generated-class method
  with the exact service name, `static`, `void`, and exactly one `IData` parameter. The parameter can
  use the imported short name or `com.wm.data.IData`, and parameter annotations are ignored for this
  shape check. Wrong signatures emit `JAVA_SOURCE_METHOD_SIGNATURE_UNSUPPORTED` and fall back to
  `java.frag` when present; multiple compatible methods emit `JAVA_SOURCE_METHOD_AMBIGUOUS`.
- M4a extracts observed Java facts from the direct service-method body. Normal control-flow blocks
  such as `if`, loops, `try/catch`, `switch`, and `synchronized` remain in scope. Lambda bodies,
  anonymous-class methods, and local-class bodies are not promoted as direct service evidence and
  emit bounded `JAVA_NESTED_EXECUTABLE_BODY_SKIPPED` findings if supported-looking API sites appear
  there. This finding does not claim the nested code never executes.
- Unbalanced or malformed complete-source class/method structure emits `JAVA_SOURCE_PARTIAL_PARSE`
  and uses `java.frag` fallback where available.
- Non-imported fully qualified type usages are an M4a limitation; referenced Java type counts cover
  imported type names observed in the direct service method.
- Observed Java pipeline accesses in the current fixtures total 73: 37 `READ` and 36 `WRITE`, with
  no `REMOVE`. Scope counts are 34 root reads, 3 nested reads, 21 root writes, and 15 nested writes.
- `pgp.services.decrypt:decryptAndVerify` contains two multiline
  `IDataUtil .get(pc, "...KeyRingCollection")` calls. Because `pc` is assigned from
  `pipeline.getCursor()`, both `publicKeyRingCollection` and `privateKeyRingCollection` are genuine
  root pipeline reads even though they are not local `svc_sig` fields.
- Current PGP Java Services contain no observed `Service.doInvoke` sites, so M4a adds no Java
  service-call edges to `graphs/dependencies.dot` for the fixture baseline.
- Current checked-in fixtures do not contain a default `processes.yml`, so the default fixture
  analysis has zero process definitions and 15 technical entrypoint candidates.

This document records observed behavior only; it is not a compatibility claim.
