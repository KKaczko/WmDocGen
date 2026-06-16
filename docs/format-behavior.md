# Newly Observed Format Behavior

Observed from current fixtures:

- Package roots can be reconstructed from directories containing `ns/` or `manifest.v3`.
- Namespace folders use `node.idf` with `node_type=interface`.
- FLOW Services use `node.ndf` with `svc_type=flow` and usually have sibling `flow.xml`.
- Java Services use `node.ndf` with `svc_type=java` and sibling `java.frag`.
- Specifications use `node.ndf` with `svc_type=spec`.
- Document types can appear as `node.ndf` with a top-level `record` containing
  `node_type=record`.
- FLOW roots observed in active fixtures use `<FLOW VERSION="3.0" CLEANUP="true">`.
- Observed FLOW Services carry signatures in `node.ndf` under `svc_sig/sig_in/sig_out`.
- Observed signature fields can carry `field_name`, `field_type`, `field_dim`, `field_opt`,
  `wrapper_type`, nested `rec_fields`, and document references in `rec_ref`.
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

This document records observed behavior only; it is not a compatibility claim.
