# pgp.services.decrypt:decryptAndVerifyString

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.decrypt` |
| Service | `decryptAndVerifyString` |
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
| `signingUserId` | `string` | 0 |  | `` |
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
| Delete operations | 18 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 4 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_7bf40b3b07f3871f` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:152` |
| `mapop_11db9932d3bd9f51` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/SecRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:308` |
| `mapop_1e92f4d27bea764c` | `/signingUserId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:452` |
| `mapop_49c47071b77ab51e` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/PubRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:622` |
| `mapop_a34bad6f639d9584` | `/encryptedString;1;0` | `/cipherTextString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:965` |
| `mapop_094509d6800b1987` | `/SecRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry/keyRegData;4;0;wx.pgp.documents:KeyRegData/secret;1;0` | `/privateKeyPassword;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1028` |
| `mapop_cc645e1e4bd865b6` | `/SecRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry/PrivateKeyData;4;0;wx.pgp.documents:PrivateKeyData/privateKeyRing;3;0` | `/privateKeyRingCollection;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1031` |
| `mapop_0592b2e90fbbf629` | `/PubRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry/PublicKeyData;4;0;wx.pgp.documents:PublicKeyData/publicKeyRing;3;0` | `/publicKeyRingCollection;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1034` |
| `mapop_9db0c97444715713` | `/plainTextString;1;0` | `/string;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1496` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_8f4a8979af4e56f5` |  | `/plainTextEncoding;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:968` |
| `mapop_046b6c6f594bd820` |  | `/outputType;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:995` |
| `mapop_fc7757dc1cb7b1a1` |  | `/verified;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1644` |
| `mapop_3e07e819f28899c6` |  | `/verified;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1772` |


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_ef7d0c55ad50aa99` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:311` |
| `mapop_51d65302263a8519` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:625` |
| `mapop_a4dc68467b746aad` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1499` |
| `mapop_129d8ee48cb2b512` | `/cipherTextString;1;0` | `/cipherTextString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1502` |
| `mapop_edd73b002d7382fc` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1505` |
| `mapop_c8156253d737dc1c` | `/plainTextEncoding;1;0` | `/plainTextEncoding;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1508` |
| `mapop_80f4befe73718383` | `/plainTextPath;1;0` | `/plainTextPath;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1511` |
| `mapop_3037476d35c97f80` | `/plainTextBytes;3.10;0` | `/plainTextBytes;3.10;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1514` |
| `mapop_fa90fe2485beac58` | `/plainTextString;1;0` | `/plainTextString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1517` |
| `mapop_59dbf98a4b79dd51` | `/plainTextStream;3;0` | `/plainTextStream;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1520` |
| `mapop_25af4aeed55772eb` | `/encryptedString;1;0` | `/encryptedString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1523` |
| `mapop_49a21d6f3d616595` | `/privateKeyRingCollection;3;0` | `/privateKeyRingCollection;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1526` |
| `mapop_ee163149d0f0efd2` | `/privateKeyPassword;1;0` | `/privateKeyPassword;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1529` |
| `mapop_d504f93eeda4e820` | `/outputType;1;0` | `/outputType;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1532` |
| `mapop_d13fe308a592c863` | `/PubRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/PubRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1535` |
| `mapop_8659d590286e3b44` | `/SecRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/SecRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1538` |
| `mapop_0c8aefc4bb7d09ea` | `/signingUserId;1;0` | `/signingUserId;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1541` |
| `mapop_5ddf6c7a0e2c4e87` | `/publicKeyRingCollection;3;0` | `/publicKeyRingCollection;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:1544` |


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
| 1 | True | `FULL` | `pgp.test.decrypt:testDecryptAndVerifyString` | `INVOKES` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyString/flow.xml:39` |
| 1 | True | `FULL` | `pgp.test.decrypt:testDecryptAndVerifyUnsignedString` | `INVOKES` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml:39` |


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_5b1fdb7a8ac5c583` | True | `FLOW` | `FULL` | `pgp.services.registry:getSecKey` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:29` |
| `call_f91396d78c6d86ff` | True | `FLOW` | `FULL` | `pgp.services.registry:getPubKey` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:316` |
| `call_9e6f16d246f99c0a` | True | `JAVA` | `FULL` | `pgp.services.decrypt:decryptAndVerify` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:630` |


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

- Service metadata: `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/node.ndf`
- INVOKE `call_5b1fdb7a8ac5c583` target `pgp.services.registry:getSecKey`:
  `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml`:29- INVOKE `call_f91396d78c6d86ff` target `pgp.services.registry:getPubKey`:
  `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml`:316- INVOKE `call_9e6f16d246f99c0a` target `pgp.services.decrypt:decryptAndVerify`:
  `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml`:630
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.