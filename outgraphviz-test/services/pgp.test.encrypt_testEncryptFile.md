# pgp.test.encrypt:testEncryptFile

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.encrypt` |
| Service | `testEncryptFile` |
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
| `mapop_40b7c8a7cc252c2b` | `/path;1;0` | `/source;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:193` |
| `mapop_201c34bb7c07e2c8` | `/path;1;0` | `/target;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:287` |
| `mapop_ca30092d4e7bf494` | `/source;1;0` | `/sourceFilename;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:438` |
| `mapop_1f857a5755b19b26` | `/target;1;0` | `/targetFilename;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:441` |
| `mapop_e932a3b55bc71cb5` | `/lastError;4;0;pub.event:exceptionInfo` | `/lastError;4;0;pub.event:exceptionInfo` |  | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:593` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_dedcc7f20e52d06f` |  | `/subDir;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:112` |
| `mapop_c66841d348456231` |  | `/fileName;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:150` |
| `mapop_4fc1c1ad50430bcb` |  | `/subDir;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:206` |
| `mapop_be30c617f71177e4` |  | `/fileName;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:244` |
| `mapop_6e6c3002e3faf773` |  | `/targetUserId;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:444` |
| `mapop_1a6f280eef3cefbc` |  | `/encryptionAlgorithm;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:472` |


## Mapping Deletes

No DELETE mapping operations were extracted.


## Transformer Bindings

| Binding | Direction | Transformer | Pipeline | Literal | Evidence |
| --- | --- | --- | --- | --- | --- |
| `bind_3500c0d052347ea5` | `INTO_TRANSFORMER` | `/subDir;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:112` |
| `bind_ce84ed97178a818a` | `INTO_TRANSFORMER` | `/fileName;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:150` |
| `bind_56356f1edf8492ca` | `FROM_TRANSFORMER` | `/path;1;0` | `/source;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:193` |
| `bind_e9898e98f6dbcb89` | `INTO_TRANSFORMER` | `/subDir;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:206` |
| `bind_34f44094ff630e7c` | `INTO_TRANSFORMER` | `/fileName;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:244` |
| `bind_605643a5be75791f` | `FROM_TRANSFORMER` | `/path;1;0` | `/target;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:287` |


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `FLOW` | `FULL` | `pgp.services.encrypt:encryptFile` |
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
| `call_174c1cab213312f4` | True | `FLOW` | `FULL` | `pgp.services.encrypt:encryptFile` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:293` |
| `call_6ec4cfff441a9a03` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:508` |


## Transformer Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_a437bb2532a46833` | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:104` |
| `call_949505d5fe4ebd7d` | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` | `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml:198` |


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
-       `fn0011` INVOKE (target=pgp.services.encrypt:encryptFile)
-         `fn0012` MAP
-     `fn0013` SEQUENCE
-       `fn0014` INVOKE (target=pub.flow:getLastError)
-         `fn0015` MAP
-         `fn0016` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/encrypt/testEncryptFile/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/encrypt/testEncryptFile/node.ndf`
- MAPINVOKE `call_a437bb2532a46833` target `pgp.services.common:getPackagePath`:
  `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`:104- MAPINVOKE `call_949505d5fe4ebd7d` target `pgp.services.common:getPackagePath`:
  `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`:198- INVOKE `call_174c1cab213312f4` target `pgp.services.encrypt:encryptFile`:
  `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`:293- INVOKE `call_6ec4cfff441a9a03` target `pub.flow:getLastError`:
  `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`:508
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.