# pgp.services.encrypt:encryptFile

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.encrypt` |
| Service | `encryptFile` |
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
| Branches | 0 |
| Loops | 0 |
| Exits | 0 |
| Call occurrences | 2 |
| Unique dependencies | 2 |

## Mapping Overview

| Metric | Count |
| --- | ---: |
| Flow maps | 3 |
| Copy operations | 5 |
| Set operations | 2 |
| Delete operations | 16 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 2 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_17e7aef9531e36a5` | `/targetUserId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:152` |
| `mapop_44914a17322c20c6` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry/PublicKeyData;4;0;wx.pgp.documents:PublicKeyData/publicKey;3;0` | `/publicKey;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:589` |
| `mapop_36c80ad12332ed3c` | `/encryptionAlgorithm;1;0` | `/encryptionAlgorithm;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:630` |
| `mapop_aa648245da847a11` | `/sourceFilename;1;0` | `/plainTextPath;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:633` |
| `mapop_b335204516538250` | `/targetFilename;1;0` | `/outputPath;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:636` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_9278b9a54709b984` |  | `/plainTextEncoding;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:592` |
| `mapop_fcd923b8fd4ed10a` |  | `/outputType;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:639` |


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_8981074fc6210387` | `/plainTextPath;1;0` | `/plainTextPath;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:677` |
| `mapop_640d23b35fcbd3b1` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:680` |
| `mapop_63a88494589d593b` | `/sourceFilename;1;0` | `/sourceFilename;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:683` |
| `mapop_39d5840322b5d51f` | `/targetFilename;1;0` | `/targetFilename;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:686` |
| `mapop_4fbe55d3bf53ed03` | `/plainTextEncoding;1;0` | `/plainTextEncoding;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:689` |
| `mapop_4560981d28742ded` | `/publicKey;3;0` | `/publicKey;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:692` |
| `mapop_dfc76bda672be7a7` | `/targetUserId;1;0` | `/targetUserId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:695` |
| `mapop_2faeb73fc4868393` | `/encryptionAlgorithm;1;0` | `/encryptionAlgorithm;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:698` |
| `mapop_844fc6edbccc0757` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:701` |
| `mapop_440ba4e4cf012443` | `/outputType;1;0` | `/outputType;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:704` |
| `mapop_ca3df647dfae2704` | `/outputPath;1;0` | `/outputPath;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:707` |
| `mapop_ea12cba62bf75961` | `/cipherTextPath;1;0` | `/cipherTextPath;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:710` |
| `mapop_a7eb21371411b75c` | `/cipherTextBytes;3.10;0` | `/cipherTextBytes;3.10;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:713` |
| `mapop_cb4a33010916aaf5` | `/cipherTextString;1;0` | `/cipherTextString;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:716` |
| `mapop_c0a665ed9bfbe36f` | `/cipherTextStream;3;0` | `/cipherTextStream;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:719` |
| `mapop_11128db3d4690a10` | `/signed;1;0` | `/signed;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:722` |


## Transformer Bindings

No MAPINVOKE transformer bindings were extracted.


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `JAVA` | `FULL` | `pgp.services.encrypt:encryptAndSign` |
| 1 | True | `FLOW` | `FULL` | `pgp.services.registry:getPubKey` |


## Transformer Dependencies

No static targets were extracted for this dependency kind.


## Called By

| Occurrences | Resolved | Target Support | Source | Kind | Source sample |
| ---: | --- | --- | --- | --- | --- |
| 1 | True | `FULL` | `pgp.test.encrypt:testEncryptFile` | `INVOKES` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:293` |


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_816b6748bb361f30` | True | `FLOW` | `FULL` | `pgp.services.registry:getPubKey` | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:29` |
| `call_99064f0c5b8d8bfa` | True | `JAVA` | `FULL` | `pgp.services.encrypt:encryptAndSign` | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:157` |


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` INVOKE (target=pgp.services.registry:getPubKey)
-     `fn0003` MAP
-   `fn0004` INVOKE (target=pgp.services.encrypt:encryptAndSign)
-     `fn0005` MAP
-     `fn0006` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/encrypt/encryptFile/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/encrypt/encryptFile/node.ndf`
- INVOKE `call_816b6748bb361f30` target `pgp.services.registry:getPubKey`:
  `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml`:29- INVOKE `call_99064f0c5b8d8bfa` target `pgp.services.encrypt:encryptAndSign`:
  `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml`:157
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.