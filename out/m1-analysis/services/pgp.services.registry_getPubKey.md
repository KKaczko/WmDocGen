# pgp.services.registry:getPubKey

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.registry` |
| Service | `getPubKey` |
| Type | `FLOW` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

## Description

No description was declared in supported metadata.

## Input Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `userId` | `string` | 0 |  | `` |


## Output Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `keyRegEntry` | `recref` | 0 |  | `pgp.documents:PubKeyRegEntry` |


## Static Invoked Services

| Invoke | Resolved | Target |
| --- | --- | --- |
| `i0001` | True | `pgp.services.common:readConfig` |
| `i0002` | True | `pgp.services.common:getPackagePath` |
| `i0003` | True | `pgp.services.keys:readPublicKeys` |

## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/registry/getPubKey/flow.xml`: FLOW element DATA is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/registry/getPubKey/flow.xml`: FLOW element MAP is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/registry/getPubKey/flow.xml`: FLOW element MAPCOPY is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/registry/getPubKey/flow.xml`: FLOW element MAPDELETE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/registry/getPubKey/flow.xml`: FLOW element MAPSET is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/registry/getPubKey/flow.xml`: FLOW element MAPSOURCE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/registry/getPubKey/flow.xml`: FLOW element MAPTARGET is observed but not interpreted in M1.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/registry/getPubKey/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/registry/getPubKey/node.ndf`
- Invoke `i0001` target `pgp.services.common:readConfig`: `PGP/ns/pgp/services/registry/getPubKey/flow.xml`
- Invoke `i0002` target `pgp.services.common:getPackagePath`: `PGP/ns/pgp/services/registry/getPubKey/flow.xml`
- Invoke `i0003` target `pgp.services.keys:readPublicKeys`: `PGP/ns/pgp/services/registry/getPubKey/flow.xml`

## Analysis Limitations

M1 extracts declared signatures, structural container paths and static `INVOKE`/`MAPINVOKE`
targets. It does not interpret MAP transformations, branch semantics, EXIT behavior, retry
semantics, dynamic invocation targets, Java code, adapter metadata, triggers or process models.