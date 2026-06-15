# pgp.services.encrypt:encryptString

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.encrypt` |
| Service | `encryptString` |
| Type | `FLOW` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

## Description

No description was declared in supported metadata.

## Input Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `encryptionAlgorithm` | `string` | 0 |  | `` |
| `string` | `string` | 0 |  | `` |
| `targetUserId` | `string` | 0 |  | `` |


## Output Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `encryptedString` | `string` | 0 |  | `` |


## Static Invoked Services

| Invoke | Resolved | Target |
| --- | --- | --- |
| `i0001` | True | `pgp.services.registry:getPubKey` |
| `i0002` | True | `pgp.services.encrypt:encryptAndSign` |

## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/encrypt/encryptString/flow.xml`: FLOW element DATA is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/encrypt/encryptString/flow.xml`: FLOW element MAP is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/encrypt/encryptString/flow.xml`: FLOW element MAPCOPY is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/encrypt/encryptString/flow.xml`: FLOW element MAPDELETE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/encrypt/encryptString/flow.xml`: FLOW element MAPSET is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/encrypt/encryptString/flow.xml`: FLOW element MAPSOURCE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/encrypt/encryptString/flow.xml`: FLOW element MAPTARGET is observed but not interpreted in M1.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/encrypt/encryptString/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/encrypt/encryptString/node.ndf`
- Invoke `i0001` target `pgp.services.registry:getPubKey`: `PGP/ns/pgp/services/encrypt/encryptString/flow.xml`
- Invoke `i0002` target `pgp.services.encrypt:encryptAndSign`: `PGP/ns/pgp/services/encrypt/encryptString/flow.xml`

## Analysis Limitations

M1 extracts declared signatures, structural container paths and static `INVOKE`/`MAPINVOKE`
targets. It does not interpret MAP transformations, branch semantics, EXIT behavior, retry
semantics, dynamic invocation targets, Java code, adapter metadata, triggers or process models.