# pgp.test.encrypt:testEncryptAndSignString

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.encrypt` |
| Service | `testEncryptAndSignString` |
| Type | `FLOW` |
| Source service type | `flow` |
| Analysis support | `FULL` |
| Description status | `DESCRIPTION_BLOCKED_SECRET` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

## Analysis Support

The artifact was analyzed by the supported parser for its service type.

## Description

Extracted description:

<redacted:secret-free-text>

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
| Call occurrences | 2 |
| Unique dependencies | 2 |

## Mapping Overview

| Metric | Count |
| --- | ---: |
| Flow maps | 3 |
| Copy operations | 1 |
| Set operations | 5 |
| Delete operations | 0 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 5 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_a24be2ff58de1d89` | `/lastError;4;0;pub.event:exceptionInfo` | `/lastError;4;0;pub.event:exceptionInfo` |  | `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/flow.xml:460` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_d6c96d83181096d1` |  | `/string;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/flow.xml:204` |
| `mapop_6e42677ac324cce4` |  | `/encryptionAlgorithm;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/flow.xml:232` |
| `mapop_ab859d9576b47e57` |  | `/signingAlgorithm;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/flow.xml:271` |
| `mapop_e23f0ee5ef142b9a` |  | `/targetUserId;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/flow.xml:311` |
| `mapop_08e1e75563f92279` |  | `/signingUserId;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/flow.xml:339` |


## Mapping Deletes

No DELETE mapping operations were extracted.


## Transformer Bindings

No MAPINVOKE transformer bindings were extracted.


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `FLOW` | `FULL` | `pgp.services.encrypt:encryptAndSignString` |
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
| `call_9ae4d58febb08e1c` | True | `FLOW` | `FULL` | `pgp.services.encrypt:encryptAndSignString` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/flow.xml:39` |
| `call_848e4626ba99e38f` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/flow.xml:375` |


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` SEQUENCE
-     `fn0003` SEQUENCE
-       `fn0004` INVOKE (target=pgp.services.encrypt:encryptAndSignString)
-         `fn0005` MAP
-     `fn0006` SEQUENCE
-       `fn0007` INVOKE (target=pub.flow:getLastError)
-         `fn0008` MAP
-         `fn0009` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/node.ndf`
- INVOKE `call_9ae4d58febb08e1c` target `pgp.services.encrypt:encryptAndSignString`:
  `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/flow.xml`:39- INVOKE `call_848e4626ba99e38f` target `pub.flow:getLastError`:
  `PGP/ns/pgp/test/encrypt/testEncryptAndSignString/flow.xml`:375
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.