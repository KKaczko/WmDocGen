# pgp.services.encrypt:encryptAndSignString

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.encrypt` |
| Service | `encryptAndSignString` |
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
| `encryptionAlgorithm` | `string` | 0 |  | `` |
| `signingAlgorithm` | `string` | 0 | True | `` |
| `signingUserId` | `string` | 0 |  | `` |
| `string` | `string` | 0 |  | `` |
| `targetUserId` | `string` | 0 |  | `` |


## Output Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `encryptedString` | `string` | 0 |  | `` |


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
| Copy operations | 11 |
| Set operations | 4 |
| Delete operations | 20 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 4 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_632761367ef0efc2` | `/targetUserId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:213` |
| `mapop_2bc5b6aafad50038` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/pubKeyEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:431` |
| `mapop_b93a4bdbf09eb3c9` | `/signingUserId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:648` |
| `mapop_fd0953ed88ecdcc5` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/secKeyEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:890` |
| `mapop_7f1772c609782784` | `/string;1;0` | `/plainTextString;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1379` |
| `mapop_bc186ffcdb947bf8` | `/encryptionAlgorithm;1;0` | `/encryptionAlgorithm;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1453` |
| `mapop_682032782d21de42` | `/signingAlgorithm;1;0` | `/signingAlgorithm;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1456` |
| `mapop_71ad5e3c44b622ec` | `/pubKeyEntry;4;0;wx.pgp.documents:PubKeyRegEntry/PublicKeyData;4;0;wx.pgp.documents:PublicKeyData/publicKey;3;0` | `/publicKey;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1459` |
| `mapop_34693246f8ede469` | `/secKeyEntry;4;0;wx.pgp.documents:SecKeyRegEntry/PrivateKeyData;4;0;wx.pgp.documents:PrivateKeyData/privateKey;3;0` | `/privateKey;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1462` |
| `mapop_283e55a52c6fe155` | `/secKeyEntry;4;0;wx.pgp.documents:SecKeyRegEntry/keyRegData;4;0;wx.pgp.documents:KeyRegData/secret;1;0` | `/privateKeyPassword;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1465` |
| `mapop_4d34733315e38c26` | `/cipherTextString;1;0` | `/encryptedString;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1986` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_dffd6bd91fe44a3c` |  | `/outputType;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1382` |
| `mapop_03f8d058264c0ea0` |  | `/plainTextEncoding;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1415` |
| `mapop_be490ed27b8ddd63` |  | `/signed;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2140` |
| `mapop_761c949da8e71897` |  | `/signed;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2268` |


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_2028681a13291f92` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:434` |
| `mapop_7ea56ef642cb7518` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:893` |
| `mapop_e08b8a9616cfe278` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1989` |
| `mapop_aa0846e6b9494e47` | `/plainTextString;1;0` | `/plainTextString;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1992` |
| `mapop_d89bdca3a31f20be` | `/encryptionAlgorithm;1;0` | `/encryptionAlgorithm;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1995` |
| `mapop_a3f9caeff4f22cc8` | `/plainTextEncoding;1;0` | `/plainTextEncoding;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:1998` |
| `mapop_06de1ee22821dcfd` | `/publicKey;3;0` | `/publicKey;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2001` |
| `mapop_722adb713621de96` | `/outputType;1;0` | `/outputType;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2004` |
| `mapop_5d9bb6a37fa14399` | `/cipherTextPath;1;0` | `/cipherTextPath;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2007` |
| `mapop_f074017980c3b3ca` | `/cipherTextBytes;3.10;0` | `/cipherTextBytes;3.10;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2010` |
| `mapop_264aadfae3156422` | `/cipherTextString;1;0` | `/cipherTextString;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2013` |
| `mapop_816266e6abe83b55` | `/cipherTextStream;3;0` | `/cipherTextStream;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2016` |
| `mapop_08ab33f14d4c0cfd` | `/string;1;0` | `/string;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2019` |
| `mapop_5f04d09e2ff1a791` | `/targetUserId;1;0` | `/targetUserId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2022` |
| `mapop_9fd2273addccd959` | `/privateKey;3;0` | `/privateKey;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2025` |
| `mapop_6054c12027dd6ee8` | `/secKeyEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/secKeyEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2028` |
| `mapop_a85565040194cbee` | `/pubKeyEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/pubKeyEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2031` |
| `mapop_d070a8f36205b4d5` | `/signingUserId;1;0` | `/signingUserId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2034` |
| `mapop_29b52549d42d2c61` | `/signingAlgorithm;1;0` | `/signingAlgorithm;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2037` |
| `mapop_fbaa372e2910cc45` | `/privateKeyPassword;1;0` | `/privateKeyPassword;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:2040` |


## Transformer Bindings

No MAPINVOKE transformer bindings were extracted.


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `JAVA` | `FULL` | `pgp.services.encrypt:encryptAndSign` |
| 1 | True | `FLOW` | `FULL` | `pgp.services.registry:getPubKey` |
| 1 | True | `FLOW` | `FULL` | `pgp.services.registry:getSecKey` |


## Transformer Dependencies

No static targets were extracted for this dependency kind.


## Called By

| Occurrences | Resolved | Target Support | Source | Kind | Source sample |
| ---: | --- | --- | --- | --- | --- |
| 1 | True | `FULL` | `pgp.test.encrypt:testEncryptAndSignString` | `INVOKES` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/flow.xml:39` |


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_f58387ec6838e62c` | True | `FLOW` | `FULL` | `pgp.services.registry:getPubKey` | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:29` |
| `call_f4ffe85a68e88597` | True | `FLOW` | `FULL` | `pgp.services.registry:getSecKey` | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:439` |
| `call_a0a5ba261df5ee85` | True | `JAVA` | `FULL` | `pgp.services.encrypt:encryptAndSign` | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:898` |


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` INVOKE (target=pgp.services.registry:getPubKey)
-     `fn0003` MAP
-     `fn0004` MAP
-   `fn0005` INVOKE (target=pgp.services.registry:getSecKey)
-     `fn0006` MAP
-     `fn0007` MAP
-   `fn0008` INVOKE (target=pgp.services.encrypt:encryptAndSign)
-     `fn0009` MAP
-     `fn0010` MAP
-   `fn0011` BRANCH (switch=/signed)
-     `fn0012` BRANCH_CASE (1)
-       `fn0013` MAP (1)
-     `fn0014` BRANCH_CASE ($default)
-       `fn0015` MAP ($default)


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/encrypt/encryptAndSignString/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/encrypt/encryptAndSignString/node.ndf`
- INVOKE `call_f58387ec6838e62c` target `pgp.services.registry:getPubKey`:
  `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml`:29- INVOKE `call_f4ffe85a68e88597` target `pgp.services.registry:getSecKey`:
  `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml`:439- INVOKE `call_a0a5ba261df5ee85` target `pgp.services.encrypt:encryptAndSign`:
  `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml`:898
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.