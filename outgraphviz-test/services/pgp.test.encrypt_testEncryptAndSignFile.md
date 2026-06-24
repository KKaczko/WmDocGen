# pgp.test.encrypt:testEncryptAndSignFile

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.encrypt` |
| Service | `testEncryptAndSignFile` |
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
| Set operations | 8 |
| Delete operations | 0 |
| Transformer bindings | 6 |
| Transformer input bindings | 4 |
| Transformer output bindings | 2 |
| Partially interpreted mappings | 8 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_9a04c81dec9d8f5a` | `/path;1;0` | `/source;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:193` |
| `mapop_977e2e4eb359bc05` | `/path;1;0` | `/target;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:287` |
| `mapop_fdde4db36bc777cb` | `/source;1;0` | `/sourceFilename;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:606` |
| `mapop_fab69820f80d7c42` | `/target;1;0` | `/targetFilename;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:609` |
| `mapop_53f2b6ca1ab02fc2` | `/lastError;4;0;pub.event:exceptionInfo` | `/lastError;4;0;pub.event:exceptionInfo` |  | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:733` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_5ab1235756cb2b87` |  | `/subDir;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:112` |
| `mapop_21c53bf7476ce7aa` |  | `/fileName;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:150` |
| `mapop_aa222bf372ba7d73` |  | `/subDir;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:206` |
| `mapop_f1558329a2b71504` |  | `/fileName;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:244` |
| `mapop_e75fa3411f63dc71` |  | `/targetUserId;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:499` |
| `mapop_cba0652224b05996` |  | `/encryptionAlgorithm;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:527` |
| `mapop_7bd08791a9d7c63a` |  | `/signingAlgorithm;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:566` |
| `mapop_a31b875e8ae6489e` |  | `/signingUserId;1;0` | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:612` |


## Mapping Deletes

No DELETE mapping operations were extracted.


## Transformer Bindings

| Binding | Direction | Transformer | Pipeline | Literal | Evidence |
| --- | --- | --- | --- | --- | --- |
| `bind_75fb4efeaad3abf9` | `INTO_TRANSFORMER` | `/subDir;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:112` |
| `bind_65f62623b042611c` | `INTO_TRANSFORMER` | `/fileName;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:150` |
| `bind_ad05d2dbc4e4cea4` | `FROM_TRANSFORMER` | `/path;1;0` | `/source;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:193` |
| `bind_e397537255a3cdaf` | `INTO_TRANSFORMER` | `/subDir;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:206` |
| `bind_6bdbf89580ad6891` | `INTO_TRANSFORMER` | `/fileName;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:244` |
| `bind_029bacea1c58a7ed` | `FROM_TRANSFORMER` | `/path;1;0` | `/target;1;0` |  | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:287` |


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `FLOW` | `FULL` | `pgp.services.encrypt:encryptAndSignFile` |
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
| `call_63131335c4952003` | True | `FLOW` | `FULL` | `pgp.services.encrypt:encryptAndSignFile` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:293` |
| `call_121a830a7b12b71f` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:648` |


## Transformer Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_c0dd7d9b9d84d2a8` | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:104` |
| `call_689a95d5e9d5eae3` | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` | `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml:198` |


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
-       `fn0011` INVOKE (target=pgp.services.encrypt:encryptAndSignFile)
-         `fn0012` MAP
-     `fn0013` SEQUENCE
-       `fn0014` INVOKE (target=pub.flow:getLastError)
-         `fn0015` MAP
-         `fn0016` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/node.ndf`
- MAPINVOKE `call_c0dd7d9b9d84d2a8` target `pgp.services.common:getPackagePath`:
  `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml`:104- MAPINVOKE `call_689a95d5e9d5eae3` target `pgp.services.common:getPackagePath`:
  `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml`:198- INVOKE `call_63131335c4952003` target `pgp.services.encrypt:encryptAndSignFile`:
  `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml`:293- INVOKE `call_121a830a7b12b71f` target `pub.flow:getLastError`:
  `PGP/ns/pgp/test/encrypt/testEncryptAndSignFile/flow.xml`:648
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.