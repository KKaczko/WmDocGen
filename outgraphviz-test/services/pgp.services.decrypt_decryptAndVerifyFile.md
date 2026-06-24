# pgp.services.decrypt:decryptAndVerifyFile

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.decrypt` |
| Service | `decryptAndVerifyFile` |
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
| `signingUserId` | `string` | 0 |  | `` |
| `sourceFilename` | `string` | 0 |  | `` |
| `targetFilename` | `string` | 0 |  | `` |
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
| Branches | 1 |
| Loops | 0 |
| Exits | 0 |
| Call occurrences | 3 |
| Unique dependencies | 3 |

## Mapping Overview

| Metric | Count |
| --- | ---: |
| Flow maps | 8 |
| Copy operations | 9 |
| Set operations | 4 |
| Delete operations | 22 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 4 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_daa1f306005d3f3f` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:152` |
| `mapop_02e8f555a909d9a3` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/SecRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:308` |
| `mapop_069aa540157b459b` | `/signingUserId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:452` |
| `mapop_4f203124686aade8` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/PubRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:622` |
| `mapop_08bacde0b90cfa04` | `/SecRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry/keyRegData;4;0;wx.pgp.documents:KeyRegData/secret;1;0` | `/privateKeyPassword;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1011` |
| `mapop_79578be946002efa` | `/SecRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry/PrivateKeyData;4;0;wx.pgp.documents:PrivateKeyData/privateKeyRing;3;0` | `/privateKeyRingCollection;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1014` |
| `mapop_9cc1adcab0592c03` | `/PubRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry/PublicKeyData;4;0;wx.pgp.documents:PublicKeyData/publicKeyRing;3;0` | `/publicKeyRingCollection;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1017` |
| `mapop_ce87c496196ea2b4` | `/sourceFilename;1;0` | `/cipherTextPath;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1020` |
| `mapop_680943994c171148` | `/targetFilename;1;0` | `/outputPath;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1023` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_be70ca2dfd033d3c` |  | `/plainTextEncoding;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:984` |
| `mapop_53cc14d3d9790a99` |  | `/outputType;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1026` |
| `mapop_d55293f8eac63908` |  | `/verified;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1716` |
| `mapop_25db707f0dec605f` |  | `/verified;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1844` |


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_e5ca5874c55881b8` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:311` |
| `mapop_2a4a93fb6b52c2bc` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:625` |
| `mapop_011e7dade29fee75` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1559` |
| `mapop_ff0aa742d0dc83c1` | `/cipherTextString;1;0` | `/cipherTextString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1562` |
| `mapop_640a09ce7678a349` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1565` |
| `mapop_48afefbf91e8c763` | `/plainTextEncoding;1;0` | `/plainTextEncoding;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1568` |
| `mapop_2c045226c56a118e` | `/plainTextPath;1;0` | `/plainTextPath;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1571` |
| `mapop_3c77f1082a47e3f1` | `/plainTextBytes;3.10;0` | `/plainTextBytes;3.10;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1574` |
| `mapop_da2a8ab35b483e5f` | `/plainTextString;1;0` | `/plainTextString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1577` |
| `mapop_a17200e763cfff3d` | `/plainTextStream;3;0` | `/plainTextStream;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1580` |
| `mapop_957bccc65888b98d` | `/encryptedString;1;0` | `/encryptedString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1583` |
| `mapop_a5f8b06248ae59ca` | `/privateKeyRingCollection;3;0` | `/privateKeyRingCollection;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1586` |
| `mapop_98bad17713b93d44` | `/privateKeyPassword;1;0` | `/privateKeyPassword;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1589` |
| `mapop_72f7d50cbc1690b4` | `/outputType;1;0` | `/outputType;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1592` |
| `mapop_ef815bd505d560b0` | `/PubRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/PubRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1595` |
| `mapop_6b4f68f20b2e66c6` | `/SecRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/SecRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1598` |
| `mapop_e29b588074b2ed77` | `/signingUserId;1;0` | `/signingUserId;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1601` |
| `mapop_0f4d1e33429e05c1` | `/publicKeyRingCollection;3;0` | `/publicKeyRingCollection;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1604` |
| `mapop_45d7c09359dc2b5c` | `/sourceFilename;1;0` | `/sourceFilename;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1607` |
| `mapop_dc9e3fa87860bab1` | `/cipherTextPath;1;0` | `/cipherTextPath;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1610` |
| `mapop_d170506e2be6bc2b` | `/targetFilename;1;0` | `/targetFilename;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1613` |
| `mapop_9bc03af0e8c684f2` | `/outputPath;1;0` | `/outputPath;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:1616` |


## Transformer Bindings

No MAPINVOKE transformer bindings were extracted.


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `JAVA` | `FULL` | `pgp.services.decrypt:decryptAndVerify` |
| 1 | True | `FLOW` | `FULL` | `pgp.services.registry:getPubKey` |
| 1 | True | `FLOW` | `FULL` | `pgp.services.registry:getSecKey` |


## Transformer Dependencies

No static targets were extracted for this dependency kind.


## Called By

| Occurrences | Resolved | Target Support | Source | Kind | Source sample |
| ---: | --- | --- | --- | --- | --- |
| 1 | True | `FULL` | `pgp.test.decrypt:testDecryptAndVerifyFile` | `INVOKES` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:293` |


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_36ffc713d2184e28` | True | `FLOW` | `FULL` | `pgp.services.registry:getSecKey` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:29` |
| `call_bf2aadecceef7b1c` | True | `FLOW` | `FULL` | `pgp.services.registry:getPubKey` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:316` |
| `call_d240a3220d584ee8` | True | `JAVA` | `FULL` | `pgp.services.decrypt:decryptAndVerify` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:630` |


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` INVOKE (target=pgp.services.registry:getSecKey)
-     `fn0003` MAP
-     `fn0004` MAP
-   `fn0005` INVOKE (target=pgp.services.registry:getPubKey)
-     `fn0006` MAP
-     `fn0007` MAP
-   `fn0008` INVOKE (target=pgp.services.decrypt:decryptAndVerify)
-     `fn0009` MAP
-     `fn0010` MAP
-   `fn0011` BRANCH (switch=/verified)
-     `fn0012` BRANCH_CASE (1)
-       `fn0013` MAP (1)
-     `fn0014` BRANCH_CASE ($default)
-       `fn0015` MAP ($default)


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/node.ndf`
- INVOKE `call_36ffc713d2184e28` target `pgp.services.registry:getSecKey`:
  `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml`:29- INVOKE `call_bf2aadecceef7b1c` target `pgp.services.registry:getPubKey`:
  `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml`:316- INVOKE `call_d240a3220d584ee8` target `pgp.services.decrypt:decryptAndVerify`:
  `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml`:630
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.