# pgp.services.encrypt:encryptString

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.encrypt` |
| Service | `encryptString` |
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
| Delete operations | 14 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 2 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_fa5cad2d052b3167` | `/targetUserId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:163` |
| `mapop_2693829fce1b26ce` | `/string;1;0` | `/plainTextString;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:592` |
| `mapop_7a69345f0ca615ed` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry/PublicKeyData;4;0;wx.pgp.documents:PublicKeyData/publicKey;3;0` | `/publicKey;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:595` |
| `mapop_30a915283ce7e918` | `/encryptionAlgorithm;1;0` | `/encryptionAlgorithm;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:669` |
| `mapop_9bf9e0756740d532` | `/cipherTextString;1;0` | `/encryptedString;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1119` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_6a2ca7205928b963` |  | `/outputType;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:598` |
| `mapop_5b95b7e6535cb181` |  | `/plainTextEncoding;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:631` |


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_ef47449b847499c7` | `/plainTextString;1;0` | `/plainTextString;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1122` |
| `mapop_1a62c42e327ee528` | `/encryptionAlgorithm;1;0` | `/encryptionAlgorithm;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1125` |
| `mapop_e3c4bdc0000ff699` | `/plainTextEncoding;1;0` | `/plainTextEncoding;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1128` |
| `mapop_92e29181cb6d4b71` | `/publicKey;3;0` | `/publicKey;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1131` |
| `mapop_1081c1ac1da31872` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` | `/keyRegEntry;4;0;wx.pgp.documents:PubKeyRegEntry` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1134` |
| `mapop_73c0f40df4769099` | `/outputType;1;0` | `/outputType;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1137` |
| `mapop_f0cce07057dc6065` | `/cipherTextPath;1;0` | `/cipherTextPath;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1140` |
| `mapop_e3a921233c92715a` | `/cipherTextBytes;3.10;0` | `/cipherTextBytes;3.10;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1143` |
| `mapop_eec784e706fdc06f` | `/cipherTextString;1;0` | `/cipherTextString;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1146` |
| `mapop_c605a4f21cbff8d8` | `/cipherTextStream;3;0` | `/cipherTextStream;3;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1149` |
| `mapop_e345881e33ce8ddc` | `/signed;1;0` | `/signed;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1152` |
| `mapop_0f782462ce842816` | `/string;1;0` | `/string;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1155` |
| `mapop_701e2989628e3a48` | `/targetUserId;1;0` | `/targetUserId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1158` |
| `mapop_a65c57ca73ebd9cc` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:1161` |


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
| 1 | True | `FULL` | `pgp.test.encrypt:testEncryptString` | `INVOKES` | `PGP/ns/pgp/test/encrypt/testEncryptString/flow.xml:39` |


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_91b437b655c3445f` | True | `FLOW` | `FULL` | `pgp.services.registry:getPubKey` | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:29` |
| `call_6d8599657a0d6595` | True | `JAVA` | `FULL` | `pgp.services.encrypt:encryptAndSign` | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:168` |


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

- Service metadata: `PGP/ns/pgp/services/encrypt/encryptString/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/encrypt/encryptString/node.ndf`
- INVOKE `call_91b437b655c3445f` target `pgp.services.registry:getPubKey`:
  `PGP/ns/pgp/services/encrypt/encryptString/flow.xml`:29- INVOKE `call_6d8599657a0d6595` target `pgp.services.encrypt:encryptAndSign`:
  `PGP/ns/pgp/services/encrypt/encryptString/flow.xml`:168
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.