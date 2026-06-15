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
- M2a treats `INVOKE` as a normal service call and `MAPINVOKE` as a transformer call. This is a
  dependency classification only; it does not imply MAP data-flow interpretation.
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
- Observed `MAP`-family elements can contain nested operations and invocations. M2a positions
  structural `MAP` nodes in the FLOW tree and extracts nested `MAPINVOKE` calls, but it does not
  interpret data movement semantics.
- `flow.xml.bak` files appear beside active FLOW files and are reported as helper backups.
- PGP contains package-name evidence that differs from the directory name: `.project` reports
  `WxPGP`, and document metadata includes `node_pkg` values such as `GCS_PGP` and `WxPGP`.

This document records observed behavior only; it is not a compatibility claim.
