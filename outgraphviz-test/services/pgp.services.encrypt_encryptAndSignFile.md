# pgp.services.encrypt:encryptAndSignFile

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.encrypt` |
| Service | `encryptAndSignFile` |
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
| `sourceFilename` | `string` | 0 |  | `` |
| `targetFilename` | `string` | 0 |  | `` |
| `targetUserId` | `string` | 0 |  | `` |


## Output Signature

No fields declared in supported metadata.


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
| Delete operations | 25 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 4 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_923cf3d304542de4` | `/targetUserId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:232` |
| `mapop_1d00bee2bf55a7d6` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/pubKeyEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:480` |
| `mapop_1e63a4f2150d64f2` | `/signingUserId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:697` |
| `mapop_73a4fcd3c85177f3` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/secKeyEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:939` |
| `mapop_c887464d01e868ec` | `/encryptionAlgorithm;1;0` | `/encryptionAlgorithm;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:1485` |
| `mapop_ddbd6f887d279b7e` | `/signingAlgorithm;1;0` | `/signingAlgorithm;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:1488` |
| `mapop_7369e5a6d5c1e0e8` | `/pubKeyEntry;4;0;wx.pgp.documents:PubKeyRegEntry/PublicKeyData;4;0;wx.pgp.documents:PublicKeyData/publicKey;3;0` | `/publicKey;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:1491` |
| `mapop_f0c078eb312931d0` | `/secKeyEntry;4;0;wx.pgp.documents:SecKeyRegEntry/PrivateKeyData;4;0;wx.pgp.documents:PrivateKeyData/privateKey;3;0` | `/privateKey;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:1494` |
| `mapop_f786264e8e648b9c` | `/secKeyEntry;4;0;wx.pgp.documents:SecKeyRegEntry/keyRegData;4;0;wx.pgp.documents:KeyRegData/secret;1;0` | `/privateKeyPassword;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:1497` |
| `mapop_9dd2d7c974392775` | `/sourceFilename;1;0` | `/plainTextPath;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:1500` |
| `mapop_11943d328e1b6109` | `/targetFilename;1;0` | `/outputPath;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:1503` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_308cec7b4eee67da` |  | `/plainTextEncoding;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:1447` |
| `mapop_dff514f3a72c436d` |  | `/outputType;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:1506` |
| `mapop_190833ff0c38cb8c` |  | `/signed;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2275` |
| `mapop_87e294e6233e40b6` |  | `/signed;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2403` |


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_ac7086d89bedad04` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:483` |
| `mapop_d43f16ec18b65315` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:942` |
| `mapop_3cd701a27a37ef60` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2109` |
| `mapop_765a2c6e7b9c4774` | `/plainTextString;1;0` | `/plainTextString;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2112` |
| `mapop_c7b8969c52562f51` | `/encryptionAlgorithm;1;0` | `/encryptionAlgorithm;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2115` |
| `mapop_fc9987897b820c3a` | `/plainTextEncoding;1;0` | `/plainTextEncoding;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2118` |
| `mapop_6cc625ff3001f64a` | `/publicKey;3;0` | `/publicKey;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2121` |
| `mapop_b9154bb247aec227` | `/outputType;1;0` | `/outputType;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2124` |
| `mapop_685d70408bf7933f` | `/cipherTextPath;1;0` | `/cipherTextPath;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2127` |
| `mapop_098fa07ef031cb1d` | `/cipherTextBytes;3.10;0` | `/cipherTextBytes;3.10;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2130` |
| `mapop_b6b80c3084a25ee0` | `/cipherTextString;1;0` | `/cipherTextString;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2133` |
| `mapop_ae13abb27b6d1658` | `/cipherTextStream;3;0` | `/cipherTextStream;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2136` |
| `mapop_a8a8f6ebe3eae590` | `/string;1;0` | `/string;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2139` |
| `mapop_ffd4f8f9317d4c71` | `/targetUserId;1;0` | `/targetUserId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2142` |
| `mapop_3eb806dbfc3258b2` | `/privateKey;3;0` | `/privateKey;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2145` |
| `mapop_451594ede9c5451d` | `/secKeyEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/secKeyEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2148` |
| `mapop_9c58b7ed296a3289` | `/pubKeyEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/pubKeyEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2151` |
| `mapop_52ff7e33e012a914` | `/signingUserId;1;0` | `/signingUserId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2154` |
| `mapop_9481a06c91d3373d` | `/signingAlgorithm;1;0` | `/signingAlgorithm;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2157` |
| `mapop_506df453e095a5f2` | `/privateKeyPassword;1;0` | `/privateKeyPassword;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2160` |
| `mapop_23a92ae5754ac0d6` | `/targetFilename;1;0` | `/targetFilename;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2163` |
| `mapop_3e42b257275122f0` | `/sourceFilename;1;0` | `/sourceFilename;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2166` |
| `mapop_926abf94665bf597` | `/encryptedString;1;0` | `/encryptedString;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2169` |
| `mapop_40373d48400534a4` | `/outputPath;1;0` | `/outputPath;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2172` |
| `mapop_739410f56b8644e2` | `/plainTextPath;1;0` | `/plainTextPath;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:2175` |


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
| 1 | True | `FULL` | `pgp.test.encrypt:testEncryptAndSignFile` | `INVOKES` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:293` |


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_27271e24a27db5a2` | True | `FLOW` | `FULL` | `pgp.services.registry:getPubKey` | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:29` |
| `call_42fe444a8c9dd6b8` | True | `FLOW` | `FULL` | `pgp.services.registry:getSecKey` | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:488` |
| `call_d2714ede39909220` | True | `JAVA` | `FULL` | `pgp.services.encrypt:encryptAndSign` | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:947` |


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

- Service metadata: `PGP/ns/pgp/services/encrypt/encryptAndSignFile/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/encrypt/encryptAndSignFile/node.ndf`
- INVOKE `call_27271e24a27db5a2` target `pgp.services.registry:getPubKey`:
  `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml`:29- INVOKE `call_42fe444a8c9dd6b8` target `pgp.services.registry:getSecKey`:
  `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml`:488- INVOKE `call_d2714ede39909220` target `pgp.services.encrypt:encryptAndSign`:
  `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml`:947
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.