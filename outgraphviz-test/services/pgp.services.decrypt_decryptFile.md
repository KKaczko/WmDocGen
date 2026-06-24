# pgp.services.decrypt:decryptFile

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.decrypt` |
| Service | `decryptFile` |
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
| Delete operations | 18 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 2 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_3414121842b89ba1` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry/PrivateKeyData;4;0;wx.pgp.documents:PrivateKeyData/privateKeyRing;3;0` | `/privateKeyRingCollection;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:388` |
| `mapop_9238fe7d16ecad60` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry/keyRegData;4;0;wx.pgp.documents:KeyRegData/secret;1;0` | `/privateKeyPassword;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:391` |
| `mapop_1cd49234a6e8aa0e` | `/sourceFilename;1;0` | `/cipherTextPath;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:394` |
| `mapop_73a6669a53fa5d5a` | `/targetFilename;1;0` | `/outputPath;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:397` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_b5119facc2b940ad` |  | `/plainTextEncoding;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:361` |
| `mapop_e1cbd196ffb6374e` |  | `/outputType;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:400` |


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_f567f183fe658686` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:902` |
| `mapop_b904e544c86b9743` | `/cipherTextString;1;0` | `/cipherTextString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:905` |
| `mapop_112c132ed11760d5` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:SecKeyRegEntry` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:908` |
| `mapop_823186c0a75f23e7` | `/plainTextEncoding;1;0` | `/plainTextEncoding;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:911` |
| `mapop_2832a9f9caa222c8` | `/plainTextPath;1;0` | `/plainTextPath;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:914` |
| `mapop_352393e9fd06d69e` | `/plainTextBytes;3.10;0` | `/plainTextBytes;3.10;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:917` |
| `mapop_fbb72dd8aaf7fd7e` | `/plainTextString;1;0` | `/plainTextString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:920` |
| `mapop_405b4206a69429a2` | `/plainTextStream;3;0` | `/plainTextStream;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:923` |
| `mapop_b2ff24f6a7435bdb` | `/verified;1;0` | `/verified;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:926` |
| `mapop_7149946f16f9c136` | `/encryptedString;1;0` | `/encryptedString;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:929` |
| `mapop_43148089fbe87e2f` | `/privateKeyRingCollection;3;0` | `/privateKeyRingCollection;3;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:932` |
| `mapop_f12810966c31509d` | `/privateKeyPassword;1;0` | `/privateKeyPassword;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:935` |
| `mapop_261c85e696cbfbcf` | `/outputType;1;0` | `/outputType;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:938` |
| `mapop_979c085e7e498e83` | `/cipherTextPath;1;0` | `/cipherTextPath;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:941` |
| `mapop_a7eba89561d3f8ca` | `/string;1;0` | `/string;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:944` |
| `mapop_e5be2385d3bbabb5` | `/outputPath;1;0` | `/outputPath;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:947` |
| `mapop_103ae4227d390598` | `/sourceFilename;1;0` | `/sourceFilename;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:950` |
| `mapop_ef3d0737e71cdb94` | `/targetFilename;1;0` | `/targetFilename;1;0` |  | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:953` |


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
| 1 | True | `FULL` | `pgp.test.decrypt:testDecryptFile` | `INVOKES` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:293` |


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_f9995119422090ec` | True | `FLOW` | `FULL` | `pgp.services.registry:getSecKey` | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:29` |
| `call_82d48e5941a4d4f1` | True | `JAVA` | `FULL` | `pgp.services.decrypt:decryptAndVerify` | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:33` |


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

- Service metadata: `PGP/ns/pgp/services/decrypt/decryptFile/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/decrypt/decryptFile/node.ndf`
- INVOKE `call_f9995119422090ec` target `pgp.services.registry:getSecKey`:
  `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml`:29- INVOKE `call_82d48e5941a4d4f1` target `pgp.services.decrypt:decryptAndVerify`:
  `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml`:33
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.