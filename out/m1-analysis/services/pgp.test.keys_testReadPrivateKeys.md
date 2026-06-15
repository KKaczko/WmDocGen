# pgp.test.keys:testReadPrivateKeys

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.keys` |
| Service | `testReadPrivateKeys` |
| Type | `FLOW` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

## Description

No description was declared in supported metadata.

## Input Signature

No fields declared in supported metadata.


## Output Signature

No fields declared in supported metadata.


## Static Invoked Services

| Invoke | Resolved | Target |
| --- | --- | --- |
| `i0001` | True | `pgp.services.registry:getSecKey` |
| `i0002` | False | `pub.flow:getLastError` |

## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/keys/testReadPrivateKeys/flow.xml`: FLOW element DATA is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/keys/testReadPrivateKeys/flow.xml`: FLOW element MAP is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/keys/testReadPrivateKeys/flow.xml`: FLOW element MAPCOPY is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/keys/testReadPrivateKeys/flow.xml`: FLOW element MAPSET is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/keys/testReadPrivateKeys/flow.xml`: FLOW element MAPSOURCE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/keys/testReadPrivateKeys/flow.xml`: FLOW element MAPTARGET is observed but not interpreted in M1.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/keys/testReadPrivateKeys/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/keys/testReadPrivateKeys/node.ndf`
- Invoke `i0001` target `pgp.services.registry:getSecKey`: `PGP/ns/pgp/test/keys/testReadPrivateKeys/flow.xml`
- Invoke `i0002` target `pub.flow:getLastError`: `PGP/ns/pgp/test/keys/testReadPrivateKeys/flow.xml`

## Analysis Limitations

M1 extracts declared signatures, structural container paths and static `INVOKE`/`MAPINVOKE`
targets. It does not interpret MAP transformations, branch semantics, EXIT behavior, retry
semantics, dynamic invocation targets, Java code, adapter metadata, triggers or process models.