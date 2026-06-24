# pgp.test.encrypt:testEncryptString

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.encrypt` |
| Service | `testEncryptString` |
| Type | `FLOW` |
| Source service type | `flow` |
| Analysis support | `FULL` |
| Description status | `SOURCE_DESCRIPTION` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

## Analysis Support

The artifact was analyzed by the supported parser for its service type.

## Description

Extracted description:

Alice sends a message to Bob
The message is encrypted with Bob's public key (available to everyone)

See http://en.wikipedia.org/wiki/Public-key_cryptography for more information on PGP

31-Mar-2011 :: Christian Schuit, Software AG :: Created

## Input Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `userId` | `string` | 0 |  | `` |


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
| Call occurrences | 2 |
| Unique dependencies | 2 |

## Mapping Overview

| Metric | Count |
| --- | ---: |
| Flow maps | 3 |
| Copy operations | 2 |
| Set operations | 2 |
| Delete operations | 0 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 2 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_56f314fa2b2dad86` | `/userId;1;0` | `/targetUserId;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptString/flow.xml:201` |
| `mapop_5caa0c47cdd2ab72` | `/lastError;4;0;pub.event:exceptionInfo` | `/lastError;4;0;pub.event:exceptionInfo` |  | `PGP/ns/pgp/test/encrypt/testEncryptString/flow.xml:450` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_ddd0b4e4ee4a70a2` |  | `/string;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptString/flow.xml:173` |
| `mapop_e03d6bc68346f325` |  | `/encryptionAlgorithm;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptString/flow.xml:204` |


## Mapping Deletes

No DELETE mapping operations were extracted.


## Transformer Bindings

No MAPINVOKE transformer bindings were extracted.


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `FLOW` | `FULL` | `pgp.services.encrypt:encryptString` |
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
| `call_573799fd50908b0c` | True | `FLOW` | `FULL` | `pgp.services.encrypt:encryptString` | `PGP/ns/pgp/test/encrypt/testEncryptString/flow.xml:39` |
| `call_cb3f678cec61b933` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` | `PGP/ns/pgp/test/encrypt/testEncryptString/flow.xml:251` |


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` SEQUENCE
-     `fn0003` SEQUENCE
-       `fn0004` INVOKE (target=pgp.services.encrypt:encryptString)
-         `fn0005` MAP
-     `fn0006` SEQUENCE
-       `fn0007` INVOKE (target=pub.flow:getLastError)
-         `fn0008` MAP
-         `fn0009` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/encrypt/testEncryptString/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/encrypt/testEncryptString/node.ndf`
- INVOKE `call_573799fd50908b0c` target `pgp.services.encrypt:encryptString`:
  `PGP/ns/pgp/test/encrypt/testEncryptString/flow.xml`:39- INVOKE `call_cb3f678cec61b933` target `pub.flow:getLastError`:
  `PGP/ns/pgp/test/encrypt/testEncryptString/flow.xml`:251
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.