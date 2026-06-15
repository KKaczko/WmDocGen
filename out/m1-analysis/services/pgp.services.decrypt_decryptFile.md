# pgp.services.decrypt:decryptFile

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.decrypt` |
| Service | `decryptFile` |
| Type | `FLOW` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

## Description

No description was declared in supported metadata.

## Input Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `sourceFilename` | `string` | 0 |  | `` |
| `targetFilename` | `string` | 0 |  | `` |
| `userId` | `string` | 0 |  | `` |


## Output Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `string` | `string` | 0 |  | `` |


## Static Invoked Services

| Invoke | Resolved | Target |
| --- | --- | --- |
| `i0001` | True | `pgp.services.registry:getSecKey` |
| `i0002` | True | `pgp.services.decrypt:decryptAndVerify` |

## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml`: FLOW element DATA is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml`: FLOW element MAP is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml`: FLOW element MAPCOPY is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml`: FLOW element MAPDELETE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml`: FLOW element MAPSET is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml`: FLOW element MAPSOURCE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml`: FLOW element MAPTARGET is observed but not interpreted in M1.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/decrypt/decryptFile/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/decrypt/decryptFile/node.ndf`
- Invoke `i0001` target `pgp.services.registry:getSecKey`: `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml`
- Invoke `i0002` target `pgp.services.decrypt:decryptAndVerify`: `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml`

## Analysis Limitations

M1 extracts declared signatures, structural container paths and static `INVOKE`/`MAPINVOKE`
targets. It does not interpret MAP transformations, branch semantics, EXIT behavior, retry
semantics, dynamic invocation targets, Java code, adapter metadata, triggers or process models.