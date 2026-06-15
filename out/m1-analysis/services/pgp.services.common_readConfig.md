# pgp.services.common:readConfig

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.common` |
| Service | `readConfig` |
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
| `key` | `recref` | 0 |  | `pgp.documents.config:KeyConfig` |


## Static Invoked Services

| Invoke | Resolved | Target |
| --- | --- | --- |
| `i0005` | True | `pgp.services.common:selectFromConfig` |
| `i0001` | False | `pub.file:getFile` |
| `i0002` | False | `pub.io:close` |
| `i0003` | False | `pub.xml:xmlStringToXMLNode` |
| `i0004` | False | `pub.xml:xmlNodeToDocument` |

## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/common/readConfig/flow.xml`: FLOW element DATA is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/common/readConfig/flow.xml`: FLOW element MAP is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/common/readConfig/flow.xml`: FLOW element MAPCOPY is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/common/readConfig/flow.xml`: FLOW element MAPDELETE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/common/readConfig/flow.xml`: FLOW element MAPSET is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/common/readConfig/flow.xml`: FLOW element MAPSOURCE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/services/common/readConfig/flow.xml`: FLOW element MAPTARGET is observed but not interpreted in M1.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/common/readConfig/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/common/readConfig/node.ndf`
- Invoke `i0001` target `pub.file:getFile`: `PGP/ns/pgp/services/common/readConfig/flow.xml`
- Invoke `i0002` target `pub.io:close`: `PGP/ns/pgp/services/common/readConfig/flow.xml`
- Invoke `i0003` target `pub.xml:xmlStringToXMLNode`: `PGP/ns/pgp/services/common/readConfig/flow.xml`
- Invoke `i0004` target `pub.xml:xmlNodeToDocument`: `PGP/ns/pgp/services/common/readConfig/flow.xml`
- Invoke `i0005` target `pgp.services.common:selectFromConfig`: `PGP/ns/pgp/services/common/readConfig/flow.xml`

## Analysis Limitations

M1 extracts declared signatures, structural container paths and static `INVOKE`/`MAPINVOKE`
targets. It does not interpret MAP transformations, branch semantics, EXIT behavior, retry
semantics, dynamic invocation targets, Java code, adapter metadata, triggers or process models.