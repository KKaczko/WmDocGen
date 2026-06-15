# pgp.test.keys:testListAlgorithms

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.keys` |
| Service | `testListAlgorithms` |
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
| `i0001` | True | `pgp.services.keys:listKeyExchangeAlgorithms` |
| `i0002` | True | `pgp.services.keys:listEncryptionAlgorithms` |
| `i0003` | True | `pgp.services.keys:listSignatureAlgorithms` |
| `i0004` | False | `pub.flow:getLastError` |

## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`: FLOW element MAP is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`: FLOW element MAPCOPY is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`: FLOW element MAPDELETE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`: FLOW element MAPSOURCE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`: FLOW element MAPTARGET is observed but not interpreted in M1.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/keys/testListAlgorithms/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/keys/testListAlgorithms/node.ndf`
- Invoke `i0001` target `pgp.services.keys:listKeyExchangeAlgorithms`: `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`
- Invoke `i0002` target `pgp.services.keys:listEncryptionAlgorithms`: `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`
- Invoke `i0003` target `pgp.services.keys:listSignatureAlgorithms`: `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`
- Invoke `i0004` target `pub.flow:getLastError`: `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`

## Analysis Limitations

M1 extracts declared signatures, structural container paths and static `INVOKE`/`MAPINVOKE`
targets. It does not interpret MAP transformations, branch semantics, EXIT behavior, retry
semantics, dynamic invocation targets, Java code, adapter metadata, triggers or process models.