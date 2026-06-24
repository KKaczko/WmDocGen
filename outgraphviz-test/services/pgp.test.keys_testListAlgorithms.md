# pgp.test.keys:testListAlgorithms

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.keys` |
| Service | `testListAlgorithms` |
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

No fields declared in supported metadata.


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
| Sequences | 3 |
| Branches | 0 |
| Loops | 0 |
| Exits | 0 |
| Call occurrences | 4 |
| Unique dependencies | 4 |

## Mapping Overview

| Metric | Count |
| --- | ---: |
| Flow maps | 8 |
| Copy operations | 4 |
| Set operations | 0 |
| Delete operations | 3 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 0 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_f030a993649b6134` | `/algorithms;1;1` | `/keyExchangeAlgorithms;1;1` |  | `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml:155` |
| `mapop_aca8bbd67c04bedb` | `/algorithms;1;1` | `/encryptionAlgorithms;1;1` |  | `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml:291` |
| `mapop_cf34759b71190b1a` | `/algorithms;1;1` | `/signatureAlgorithms;1;1` |  | `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml:439` |
| `mapop_e1faf42981a1e827` | `/lastError;4;0;pub.event:exceptionInfo` | `/lastError;4;0;pub.event:exceptionInfo` |  | `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml:538` |


## Mapping Sets

No SET mapping operations were extracted.


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_bb277e9de6798c34` | `/algorithms;1;1` | `/algorithms;1;1` |  | `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml:158` |
| `mapop_f07bc93b6f2bcc4f` | `/algorithms;1;1` | `/algorithms;1;1` |  | `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml:294` |
| `mapop_5dc7b0830d52248e` | `/algorithms;1;1` | `/algorithms;1;1` |  | `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml:442` |


## Transformer Bindings

No MAPINVOKE transformer bindings were extracted.


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `JAVA` | `FULL` | `pgp.services.keys:listEncryptionAlgorithms` |
| 1 | True | `JAVA` | `FULL` | `pgp.services.keys:listKeyExchangeAlgorithms` |
| 1 | True | `JAVA` | `FULL` | `pgp.services.keys:listSignatureAlgorithms` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` |


## Transformer Dependencies

No static targets were extracted for this dependency kind.


## Called By

No incoming static service calls target this service.


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_a44648f81a04587a` | True | `JAVA` | `FULL` | `pgp.services.keys:listKeyExchangeAlgorithms` | `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml:39` |
| `call_d4505890e7dcf0eb` | True | `JAVA` | `FULL` | `pgp.services.keys:listEncryptionAlgorithms` | `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml:163` |
| `call_c9eeb695f57daf85` | True | `JAVA` | `FULL` | `pgp.services.keys:listSignatureAlgorithms` | `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml:299` |
| `call_237adb496bc5991d` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` | `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml:453` |


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` SEQUENCE
-     `fn0003` SEQUENCE
-       `fn0004` INVOKE (target=pgp.services.keys:listKeyExchangeAlgorithms)
-         `fn0005` MAP
-         `fn0006` MAP
-       `fn0007` INVOKE (target=pgp.services.keys:listEncryptionAlgorithms)
-         `fn0008` MAP
-         `fn0009` MAP
-       `fn0010` INVOKE (target=pgp.services.keys:listSignatureAlgorithms)
-         `fn0011` MAP
-         `fn0012` MAP
-     `fn0013` SEQUENCE
-       `fn0014` INVOKE (target=pub.flow:getLastError)
-         `fn0015` MAP
-         `fn0016` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/keys/testListAlgorithms/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/keys/testListAlgorithms/node.ndf`
- INVOKE `call_a44648f81a04587a` target `pgp.services.keys:listKeyExchangeAlgorithms`:
  `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`:39- INVOKE `call_d4505890e7dcf0eb` target `pgp.services.keys:listEncryptionAlgorithms`:
  `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`:163- INVOKE `call_c9eeb695f57daf85` target `pgp.services.keys:listSignatureAlgorithms`:
  `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`:299- INVOKE `call_237adb496bc5991d` target `pub.flow:getLastError`:
  `PGP/ns/pgp/test/keys/testListAlgorithms/flow.xml`:453
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.