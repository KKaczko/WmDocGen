# pgp.services.decrypt:decryptString

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.decrypt` |
| Service | `decryptString` |
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
| `encryptedString` | `string` | 0 |  | `` |
| `userId` | `string` | 0 |  | `` |


## Output Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `string` | `string` | 0 |  | `` |


## Document Type Usage

### Input Document Types

No document dependencies were extracted for this usage role.


### Output Document Types

No document dependencies were extracted for this usage role.


### Resolved Document References

No document reference occurrences were extracted for this section.


### Unresolved Document References

No document reference occurrences were extracted for this section.



## FLOW Overview

| Metric | Count |
| --- | ---: |
| Sequences | 0 |
| Branches | 0 |
| Loops | 0 |
| Exits | 0 |
| Call occurrences | 2 |
| Unique dependencies | 2 |

## Mapping Overview

| Metric | Count |
| --- | ---: |
| Flow maps | 2 |
| Copy operations | 4 |
| Set operations | 2 |
| Delete operations | 13 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 2 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_04a5e13c21ee6c5f` | `/encryptedString;1;0` | `/cipherTextString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:342` |
| `mapop_e9478bf785b710c7` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry/PrivateKeyData;4;0;wx.pgp.documents:PrivateKeyData/privateKeyRing;3;0` | `/privateKeyRingCollection;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:372` |
| `mapop_33144917f279a841` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry/keyRegData;4;0;wx.pgp.documents:KeyRegData/secret;1;0` | `/privateKeyPassword;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:375` |
| `mapop_a5aa8147edbbcfe7` | `/plainTextString;1;0` | `/string;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:828` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_6bfb1f58799dbf65` |  | `/plainTextEncoding;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:345` |
| `mapop_52fe175966129467` |  | `/outputType;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:378` |


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_215f96757698c8bf` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:831` |
| `mapop_3b9d478a297d0c00` | `/cipherTextString;1;0` | `/cipherTextString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:834` |
| `mapop_2d9fa7fe3ba6b3d0` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:837` |
| `mapop_9127e066728e55e0` | `/plainTextEncoding;1;0` | `/plainTextEncoding;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:840` |
| `mapop_ee81a9708652c190` | `/plainTextPath;1;0` | `/plainTextPath;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:843` |
| `mapop_aff69021eab84777` | `/plainTextBytes;3.10;0` | `/plainTextBytes;3.10;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:846` |
| `mapop_aef514e12976c0f9` | `/plainTextString;1;0` | `/plainTextString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:849` |
| `mapop_9cfbc9314ee91025` | `/plainTextStream;3;0` | `/plainTextStream;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:852` |
| `mapop_c476bd695644a93b` | `/verified;1;0` | `/verified;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:855` |
| `mapop_3ebe2adcb956e0c0` | `/encryptedString;1;0` | `/encryptedString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:858` |
| `mapop_7dbf791db827573f` | `/privateKeyRingCollection;3;0` | `/privateKeyRingCollection;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:861` |
| `mapop_4e2fb71cdb8713be` | `/privateKeyPassword;1;0` | `/privateKeyPassword;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:864` |
| `mapop_073a44842207affe` | `/outputType;1;0` | `/outputType;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:867` |


## Transformer Bindings

No MAPINVOKE transformer bindings were extracted.


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `JAVA` | `FULL` | `pgp.services.decrypt:decryptAndVerify` |
| 1 | True | `FLOW` | `FULL` | `pgp.services.registry:getSecKey` |


## Transformer Dependencies

No static targets were extracted for this dependency kind.


## Called By

| Occurrences | Resolved | Target Support | Source | Kind | Source sample |
| ---: | --- | --- | --- | --- | --- |
| 1 | True | `FULL` | `pgp.test.decrypt:testDecryptString` | `INVOKES` | `PGP/ns/pgp/test/decrypt/testDecryptString/flow.xml:39` |


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_1644d3a4fa7494fd` | True | `FLOW` | `FULL` | `pgp.services.registry:getSecKey` | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:29` |
| `call_ae2f7d5b9d846191` | True | `JAVA` | `FULL` | `pgp.services.decrypt:decryptAndVerify` | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:33` |


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` INVOKE (target=pgp.services.registry:getSecKey)
-   `fn0003` INVOKE (target=pgp.services.decrypt:decryptAndVerify)
-     `fn0004` MAP
-     `fn0005` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/decrypt/decryptString/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/decrypt/decryptString/node.ndf`
- INVOKE `call_1644d3a4fa7494fd` target `pgp.services.registry:getSecKey`:
  `PGP/ns/pgp/services/decrypt/decryptString/flow.xml`:29- INVOKE `call_ae2f7d5b9d846191` target `pgp.services.decrypt:decryptAndVerify`:
  `PGP/ns/pgp/services/decrypt/decryptString/flow.xml`:33
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.