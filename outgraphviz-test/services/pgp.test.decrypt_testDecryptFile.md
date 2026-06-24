# pgp.test.decrypt:testDecryptFile

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.decrypt` |
| Service | `testDecryptFile` |
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
| Call occurrences | 4 |
| Unique dependencies | 3 |

## Mapping Overview

| Metric | Count |
| --- | ---: |
| Flow maps | 8 |
| Copy operations | 5 |
| Set operations | 5 |
| Delete operations | 0 |
| Transformer bindings | 6 |
| Transformer input bindings | 4 |
| Transformer output bindings | 2 |
| Partially interpreted mappings | 5 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_5f139785806402b0` | `/path;1;0` | `/target;1;0` |  | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:193` |
| `mapop_b1cb1a97942a0717` | `/path;1;0` | `/source;1;0` |  | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:287` |
| `mapop_7060adeb223bc169` | `/source;1;0` | `/sourceFilename;1;0` |  | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:447` |
| `mapop_7b32c4a755ba8c96` | `/target;1;0` | `/targetFilename;1;0` |  | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:450` |
| `mapop_dcef3aacfdc070da` | `/lastError;4;0;pub.event:exceptionInfo` | `/lastError;4;0;pub.event:exceptionInfo` |  | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:656` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_7501e0e55aef1b05` |  | `/subDir;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:112` |
| `mapop_f2f2c8fa7bf2d0d0` |  | `/fileName;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:150` |
| `mapop_df4587280d8fc396` |  | `/subDir;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:206` |
| `mapop_1999fbbd3b287f31` |  | `/fileName;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:244` |
| `mapop_d85506c1c33cf3be` |  | `/userId;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:419` |


## Mapping Deletes

No DELETE mapping operations were extracted.


## Transformer Bindings

| Binding | Direction | Transformer | Pipeline | Literal | Evidence |
| --- | --- | --- | --- | --- | --- |
| `bind_ca641ab307437b2b` | `INTO_TRANSFORMER` | `/subDir;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:112` |
| `bind_40b5d4f48620c1e5` | `INTO_TRANSFORMER` | `/fileName;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:150` |
| `bind_4c1e09dd29d60c74` | `FROM_TRANSFORMER` | `/path;1;0` | `/target;1;0` |  | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:193` |
| `bind_95f577a893387024` | `INTO_TRANSFORMER` | `/subDir;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:206` |
| `bind_44da2012a97cfc86` | `INTO_TRANSFORMER` | `/fileName;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:244` |
| `bind_e30632b711f42597` | `FROM_TRANSFORMER` | `/path;1;0` | `/source;1;0` |  | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:287` |


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `FLOW` | `FULL` | `pgp.services.decrypt:decryptFile` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` |


## Transformer Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 2 | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` |


## Called By

No incoming static service calls target this service.


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_3cf2fbcb74ca6f92` | True | `FLOW` | `FULL` | `pgp.services.decrypt:decryptFile` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:293` |
| `call_4d358376b9551c11` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:461` |


## Transformer Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_19dd06cc63230b9e` | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:104` |
| `call_5026aa953d320982` | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` | `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml:198` |


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` SEQUENCE
-     `fn0003` SEQUENCE
-       `fn0004` MAP
-         `fn0005` MAPINVOKE (target=pgp.services.common:getPackagePath)
-           `fn0006` MAP
-           `fn0007` MAP
-         `fn0008` MAPINVOKE (target=pgp.services.common:getPackagePath)
-           `fn0009` MAP
-           `fn0010` MAP
-       `fn0011` INVOKE (target=pgp.services.decrypt:decryptFile)
-         `fn0012` MAP
-     `fn0013` SEQUENCE
-       `fn0014` INVOKE (target=pub.flow:getLastError)
-         `fn0015` MAP
-         `fn0016` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/decrypt/testDecryptFile/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/decrypt/testDecryptFile/node.ndf`
- MAPINVOKE `call_19dd06cc63230b9e` target `pgp.services.common:getPackagePath`:
  `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml`:104- MAPINVOKE `call_5026aa953d320982` target `pgp.services.common:getPackagePath`:
  `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml`:198- INVOKE `call_3cf2fbcb74ca6f92` target `pgp.services.decrypt:decryptFile`:
  `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml`:293- INVOKE `call_4d358376b9551c11` target `pub.flow:getLastError`:
  `PGP/ns/pgp/test/decrypt/testDecryptFile/flow.xml`:461
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.