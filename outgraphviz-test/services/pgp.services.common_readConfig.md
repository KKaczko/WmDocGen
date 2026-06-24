# pgp.services.common:readConfig

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.common` |
| Service | `readConfig` |
| Type | `FLOW` |
| Source service type | `flow` |
| Analysis support | `FULL` |
| Description status | `NO_DESCRIPTION` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

## Analysis Support

The artifact was analyzed by the supported parser for its service type.

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


## Document Type Usage

### Input Document Types

No document dependencies were extracted for this usage role.


### Output Document Types

| Usage | Resolved | Document | Occurrences |
| --- | --- | --- | ---: |
| `OUTPUT` | True | [`pgp.documents.config:KeyConfig`](../documents/pgp.documents.config_KeyConfig.md) | 1 |


### Resolved Document References

| Usage | Field | Resolved | Target | Source |
| --- | --- | --- | --- | --- |
| `OUTPUT` | `key` | True | [`pgp.documents.config:KeyConfig`](../documents/pgp.documents.config_KeyConfig.md) | `PGP/ns/pgp/services/common/readConfig/node.ndf:52` |


### Unresolved Document References

No document reference occurrences were extracted for this section.



## FLOW Overview

| Metric | Count |
| --- | ---: |
| Sequences | 0 |
| Branches | 0 |
| Loops | 0 |
| Exits | 0 |
| Call occurrences | 5 |
| Unique dependencies | 5 |

## Mapping Overview

| Metric | Count |
| --- | ---: |
| Flow maps | 11 |
| Copy operations | 3 |
| Set operations | 4 |
| Delete operations | 11 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 4 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_1fb799e030d93b14` | `/body;2;0/stream;3;0` | `/inputStream;3;0` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:420` |
| `mapop_a0075b555853bbff` | `/body;2;0/string;1;0` | `/xmldata;1;0` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:705` |
| `mapop_826c13d4f23e507f` | `/document;2;0` | `/config;4;0;wx.pgp.documents:PGPconfig` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:1290` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_a11665abc123d7aa` |  | `/loadAs;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/common/readConfig/flow.xml:130` |
| `mapop_daa3717ea30fa2d7` |  | `/filename;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/common/readConfig/flow.xml:157` |
| `mapop_a2de5f5280daa781` |  | `/makeArrays;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/common/readConfig/flow.xml:1066` |
| `mapop_d2f4417d8787fcab` |  | `/arrays;1;1` | `<redacted:literal>` | `PGP/ns/pgp/services/common/readConfig/flow.xml:1091` |


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_0873c1c9ef9bbf3f` | `/loadAs;1;0` | `/loadAs;1;0` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:277` |
| `mapop_e022376e33896ea3` | `/filename;1;0` | `/filename;1;0` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:280` |
| `mapop_fbda3146fcd0d889` | `/inputStream;3;0` | `/inputStream;3;0` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:492` |
| `mapop_be3dafa208684821` | `/body;2;0` | `/body;2;0` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:837` |
| `mapop_e8a84fb2dc13556e` | `/xmldata;1;0` | `/xmldata;1;0` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:840` |
| `mapop_edaf59c911d23786` | `/node;3;0` | `/node;3;0` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:1208` |
| `mapop_a470d843e95ee095` | `/makeArrays;1;0` | `/makeArrays;1;0` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:1211` |
| `mapop_6a6feb8826307914` | `/arrays;1;1` | `/arrays;1;1` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:1214` |
| `mapop_222dd874f9418bba` | `/document;2;0` | `/document;2;0` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:1293` |
| `mapop_5699193dd5a3d20a` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:1309` |
| `mapop_4c6303c7a0f9b3f4` | `/config;4;0;wx.pgp.documents:PGPconfig` | `/config;4;0;wx.pgp.documents:PGPconfig` |  | `PGP/ns/pgp/services/common/readConfig/flow.xml:1312` |


## Transformer Bindings

No MAPINVOKE transformer bindings were extracted.


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `JAVA` | `FULL` | `pgp.services.common:selectFromConfig` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `pub.file:getFile` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `pub.io:close` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `pub.xml:xmlNodeToDocument` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `pub.xml:xmlStringToXMLNode` |


## Transformer Dependencies

No static targets were extracted for this dependency kind.


## Called By

| Occurrences | Resolved | Target Support | Source | Kind | Source sample |
| ---: | --- | --- | --- | --- | --- |
| 1 | True | `FULL` | `pgp.services.registry:getPubKey` | `INVOKES` | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:29` |
| 1 | True | `FULL` | `pgp.services.registry:getSecKey` | `INVOKES` | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:29` |


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_015413d193efc943` | False | `UNKNOWN` | `UNKNOWN` | `pub.file:getFile` | `PGP/ns/pgp/services/common/readConfig/flow.xml:29` |
| `call_f56f8b5cab4ed3ba` | False | `UNKNOWN` | `UNKNOWN` | `pub.io:close` | `PGP/ns/pgp/services/common/readConfig/flow.xml:285` |
| `call_c6f9328027562cdd` | False | `UNKNOWN` | `UNKNOWN` | `pub.xml:xmlStringToXMLNode` | `PGP/ns/pgp/services/common/readConfig/flow.xml:497` |
| `call_f59a1685ff3049bb` | False | `UNKNOWN` | `UNKNOWN` | `pub.xml:xmlNodeToDocument` | `PGP/ns/pgp/services/common/readConfig/flow.xml:845` |
| `call_e8102911363a2dcf` | True | `JAVA` | `FULL` | `pgp.services.common:selectFromConfig` | `PGP/ns/pgp/services/common/readConfig/flow.xml:1297` |


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` INVOKE (target=pub.file:getFile)
-     `fn0003` MAP
-     `fn0004` MAP
-   `fn0005` INVOKE (target=pub.io:close)
-     `fn0006` MAP
-     `fn0007` MAP
-   `fn0008` INVOKE (target=pub.xml:xmlStringToXMLNode)
-     `fn0009` MAP
-     `fn0010` MAP
-   `fn0011` INVOKE (target=pub.xml:xmlNodeToDocument)
-     `fn0012` MAP
-     `fn0013` MAP
-   `fn0014` MAP
-   `fn0015` INVOKE (target=pgp.services.common:selectFromConfig)
-     `fn0016` MAP
-     `fn0017` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/common/readConfig/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/common/readConfig/node.ndf`
- INVOKE `call_015413d193efc943` target `pub.file:getFile`:
  `PGP/ns/pgp/services/common/readConfig/flow.xml`:29- INVOKE `call_f56f8b5cab4ed3ba` target `pub.io:close`:
  `PGP/ns/pgp/services/common/readConfig/flow.xml`:285- INVOKE `call_c6f9328027562cdd` target `pub.xml:xmlStringToXMLNode`:
  `PGP/ns/pgp/services/common/readConfig/flow.xml`:497- INVOKE `call_f59a1685ff3049bb` target `pub.xml:xmlNodeToDocument`:
  `PGP/ns/pgp/services/common/readConfig/flow.xml`:845- INVOKE `call_e8102911363a2dcf` target `pgp.services.common:selectFromConfig`:
  `PGP/ns/pgp/services/common/readConfig/flow.xml`:1297
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.