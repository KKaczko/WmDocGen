# pgp.test.decrypt:testDecryptAndVerifyFile

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.decrypt` |
| Service | `testDecryptAndVerifyFile` |
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
| Set operations | 6 |
| Delete operations | 0 |
| Transformer bindings | 6 |
| Transformer input bindings | 4 |
| Transformer output bindings | 2 |
| Partially interpreted mappings | 6 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_31056ac2cedeb2dc` | `/path;1;0` | `/target;1;0` |  | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:193` |
| `mapop_b05a1d3e42b442da` | `/path;1;0` | `/source;1;0` |  | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:287` |
| `mapop_cd1edfca99952cb5` | `/source;1;0` | `/sourceFilename;1;0` |  | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:494` |
| `mapop_78fdf8865587c3ad` | `/target;1;0` | `/targetFilename;1;0` |  | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:497` |
| `mapop_532351918e067343` | `/lastError;4;0;pub.event:exceptionInfo` | `/lastError;4;0;pub.event:exceptionInfo` |  | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:703` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_1cc354972e3db4d9` |  | `/subDir;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:112` |
| `mapop_6f368137bce308e8` |  | `/fileName;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:150` |
| `mapop_3d85bd3562ad7ab8` |  | `/subDir;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:206` |
| `mapop_9e958165f940b8be` |  | `/fileName;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:244` |
| `mapop_587217d0820da240` |  | `/userId;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:438` |
| `mapop_c4e535c24281ad59` |  | `/signingUserId;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:466` |


## Mapping Deletes

No DELETE mapping operations were extracted.


## Transformer Bindings

| Binding | Direction | Transformer | Pipeline | Literal | Evidence |
| --- | --- | --- | --- | --- | --- |
| `bind_8e252495a02b0f1f` | `INTO_TRANSFORMER` | `/subDir;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:112` |
| `bind_e3376a19a1a81e4b` | `INTO_TRANSFORMER` | `/fileName;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:150` |
| `bind_69a9430e1d518e0f` | `FROM_TRANSFORMER` | `/path;1;0` | `/target;1;0` |  | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:193` |
| `bind_d7703867e07ac81e` | `INTO_TRANSFORMER` | `/subDir;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:206` |
| `bind_c5b6553eea3d738f` | `INTO_TRANSFORMER` | `/fileName;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:244` |
| `bind_73d37579419bf6d0` | `FROM_TRANSFORMER` | `/path;1;0` | `/source;1;0` |  | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:287` |


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `FLOW` | `FULL` | `pgp.services.decrypt:decryptAndVerifyFile` |
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
| `call_7b017b60aace09ad` | True | `FLOW` | `FULL` | `pgp.services.decrypt:decryptAndVerifyFile` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:293` |
| `call_c5177a5cdade28b6` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:508` |


## Transformer Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_bb58ac0c1ed74b45` | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:104` |
| `call_e4143c91436766b4` | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` | `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml:198` |


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
-       `fn0011` INVOKE (target=pgp.services.decrypt:decryptAndVerifyFile)
-         `fn0012` MAP
-     `fn0013` SEQUENCE
-       `fn0014` INVOKE (target=pub.flow:getLastError)
-         `fn0015` MAP
-         `fn0016` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/node.ndf`
- MAPINVOKE `call_bb58ac0c1ed74b45` target `pgp.services.common:getPackagePath`:
  `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml`:104- MAPINVOKE `call_e4143c91436766b4` target `pgp.services.common:getPackagePath`:
  `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml`:198- INVOKE `call_7b017b60aace09ad` target `pgp.services.decrypt:decryptAndVerifyFile`:
  `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml`:293- INVOKE `call_c5177a5cdade28b6` target `pub.flow:getLastError`:
  `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyFile/flow.xml`:508
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.