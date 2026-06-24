# pgp.test.decrypt:testDecryptAndVerifyUnsignedString

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.decrypt` |
| Service | `testDecryptAndVerifyUnsignedString` |
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
| Set operations | 3 |
| Delete operations | 0 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 3 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_a860bf2b05884a03` | `/lastError;4;0;pub.event:exceptionInfo` | `/lastError;4;0;pub.event:exceptionInfo` |  | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml:443` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_738b698a77aef986` |  | `/encryptedString;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml:143` |
| `mapop_41521b128ad7e249` |  | `/userId;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml:184` |
| `mapop_bc09cd4b3883498f` |  | `/signingUserId;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml:212` |


## Mapping Deletes

No DELETE mapping operations were extracted.


## Transformer Bindings

No MAPINVOKE transformer bindings were extracted.


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `FLOW` | `FULL` | `pgp.services.decrypt:decryptAndVerifyString` |
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
| `call_c2516784a2c2bdd9` | True | `FLOW` | `FULL` | `pgp.services.decrypt:decryptAndVerifyString` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml:39` |
| `call_68211549f6aed93f` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml:248` |


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` SEQUENCE
-     `fn0003` SEQUENCE
-       `fn0004` INVOKE (target=pgp.services.decrypt:decryptAndVerifyString)
-         `fn0005` MAP
-     `fn0006` SEQUENCE
-       `fn0007` INVOKE (target=pub.flow:getLastError)
-         `fn0008` MAP
-         `fn0009` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/node.ndf`
- INVOKE `call_c2516784a2c2bdd9` target `pgp.services.decrypt:decryptAndVerifyString`:
  `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml`:39- INVOKE `call_68211549f6aed93f` target `pub.flow:getLastError`:
  `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml`:248
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.