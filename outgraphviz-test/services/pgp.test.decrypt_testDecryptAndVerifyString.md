# pgp.test.decrypt:testDecryptAndVerifyString

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.decrypt` |
| Service | `testDecryptAndVerifyString` |
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
| `mapop_c89e7f6c0ef5213a` | `/lastError;4;0;pub.event:exceptionInfo` | `/lastError;4;0;pub.event:exceptionInfo` |  | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyString/flow.xml:450` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_639b8a7636c975df` |  | `/encryptedString;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyString/flow.xml:143` |
| `mapop_2f0172060d78bfb6` |  | `/userId;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyString/flow.xml:191` |
| `mapop_df5a6689f3ae9fa5` |  | `/signingUserId;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyString/flow.xml:219` |


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
| `call_68d3aa4e7af2856a` | True | `FLOW` | `FULL` | `pgp.services.decrypt:decryptAndVerifyString` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyString/flow.xml:39` |
| `call_fe96911475ec147d` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyString/flow.xml:255` |


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

- Service metadata: `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyString/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyString/node.ndf`
- INVOKE `call_68d3aa4e7af2856a` target `pgp.services.decrypt:decryptAndVerifyString`:
  `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyString/flow.xml`:39- INVOKE `call_fe96911475ec147d` target `pub.flow:getLastError`:
  `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyString/flow.xml`:255
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.