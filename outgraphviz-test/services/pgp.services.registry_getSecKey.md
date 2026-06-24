# pgp.services.registry:getSecKey

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.registry` |
| Service | `getSecKey` |
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
| `userId` | `string` | 0 |  | `` |


## Output Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `keyRegEntry` | `recref` | 0 |  | `pgp.documents:SecKeyRegEntry` |


## Document Type Usage

### Input Document Types

No document dependencies were extracted for this usage role.


### Output Document Types

| Usage | Resolved | Document | Occurrences |
| --- | --- | --- | ---: |
| `OUTPUT` | True | [`pgp.documents:SecKeyRegEntry`](../documents/pgp.documents_SecKeyRegEntry.md) | 1 |


### Resolved Document References

| Usage | Field | Resolved | Target | Source |
| --- | --- | --- | --- | --- |
| `OUTPUT` | `keyRegEntry` | True | [`pgp.documents:SecKeyRegEntry`](../documents/pgp.documents_SecKeyRegEntry.md) | `PGP/ns/pgp/services/registry/getSecKey/node.ndf:52` |


### Unresolved Document References

No document reference occurrences were extracted for this section.



## FLOW Overview

| Metric | Count |
| --- | ---: |
| Sequences | 0 |
| Branches | 0 |
| Loops | 0 |
| Exits | 0 |
| Call occurrences | 3 |
| Unique dependencies | 3 |

## Mapping Overview

| Metric | Count |
| --- | ---: |
| Flow maps | 7 |
| Copy operations | 7 |
| Set operations | 1 |
| Delete operations | 5 |
| Transformer bindings | 3 |
| Transformer input bindings | 2 |
| Transformer output bindings | 1 |
| Partially interpreted mappings | 1 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_fc3aa1cc93c4ac90` | `/key;4;0;wx.pgp.documents.config:KeyConfig/sec;2;0/filename;1;0` | `/fileName;1;0` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:169` |
| `mapop_687e96fed8176da2` | `/path;1;0` | `/path;1;0` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:215` |
| `mapop_91d7823a1dcf6a05` | `/key;4;0;wx.pgp.documents:KeyConfig/sec;2;0/secret;1;0` | `/password;1;0` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:355` |
| `mapop_4aeb5b88fc31d127` | `/privateKeyData;4;0;pgp.documents:PrivateKeyData` | `/keyRegEntry;4;0;pgp.documents:SecKeyRegEntry/PrivateKeyData;4;0;pgp.documents:PrivateKeyData` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:591` |
| `mapop_0df1506c99148f62` | `/key;4;0;pgp.documents.config:KeyConfig/@userId;1;0` | `/keyRegEntry;4;0;pgp.documents:SecKeyRegEntry/keyRegData;4;0;pgp.documents:KeyRegData/@UserId;1;0` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:594` |
| `mapop_f84ae78b69f85417` | `/key;4;0;pgp.documents.config:KeyConfig/sec;2;0/secret;1;0` | `/keyRegEntry;4;0;pgp.documents:SecKeyRegEntry/keyRegData;4;0;pgp.documents:KeyRegData/secret;1;0` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:597` |
| `mapop_88cf37b91d259c06` | `/path;1;0` | `/keyRegEntry;4;0;pgp.documents:SecKeyRegEntry/keyRegData;4;0;pgp.documents:KeyRegData/KeyPath;1;0` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:600` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_da9198db8cfcf99e` |  | `/subDir;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:172` |


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_c64088fb803c78d8` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:38` |
| `mapop_8f4b5f1c2dceaeb8` | `/password;1;0` | `/password;1;0` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:463` |
| `mapop_4e0e5f02f322aceb` | `/key;4;0;pgp.documents.config:KeyConfig` | `/key;4;0;pgp.documents.config:KeyConfig` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:582` |
| `mapop_533d3b44b8eed8d1` | `/privateKeyData;4;0;pgp.documents:PrivateKeyData` | `/privateKeyData;4;0;pgp.documents:PrivateKeyData` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:585` |
| `mapop_a85238e1e734c752` | `/path;1;0` | `/path;1;0` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:588` |


## Transformer Bindings

| Binding | Direction | Transformer | Pipeline | Literal | Evidence |
| --- | --- | --- | --- | --- | --- |
| `bind_eeeac0ebc9960f87` | `INTO_TRANSFORMER` | `/fileName;1;0` | `/key;4;0;wx.pgp.documents.config:KeyConfig/sec;2;0/filename;1;0` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:169` |
| `bind_bcd87eac3aa77826` | `INTO_TRANSFORMER` | `/subDir;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:172` |
| `bind_5180edc5642b787f` | `FROM_TRANSFORMER` | `/path;1;0` | `/path;1;0` |  | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:215` |


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `FLOW` | `FULL` | `pgp.services.common:readConfig` |
| 1 | True | `JAVA` | `FULL` | `pgp.services.keys:readPrivateKeys` |


## Transformer Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` |


## Called By

| Occurrences | Resolved | Target Support | Source | Kind | Source sample |
| ---: | --- | --- | --- | --- | --- |
| 1 | True | `FULL` | `pgp.services.decrypt:decryptAndVerifyFile` | `INVOKES` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:29` |
| 1 | True | `FULL` | `pgp.services.decrypt:decryptAndVerifyString` | `INVOKES` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:29` |
| 1 | True | `FULL` | `pgp.services.decrypt:decryptFile` | `INVOKES` | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:29` |
| 1 | True | `FULL` | `pgp.services.decrypt:decryptString` | `INVOKES` | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:29` |
| 1 | True | `FULL` | `pgp.services.encrypt:encryptAndSignFile` | `INVOKES` | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:488` |
| 1 | True | `FULL` | `pgp.services.encrypt:encryptAndSignString` | `INVOKES` | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:439` |
| 1 | True | `FULL` | `pgp.test.keys:testReadPrivateKeys` | `INVOKES` | `PGP/ns/pgp/test/keys/testReadPrivateKeys/flow.xml:39` |


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_3d98a0adeb48fea5` | True | `FLOW` | `FULL` | `pgp.services.common:readConfig` | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:29` |
| `call_e049b2e3556f0c74` | True | `JAVA` | `FULL` | `pgp.services.keys:readPrivateKeys` | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:221` |


## Transformer Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_03e298c99dd41e00` | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:161` |


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` INVOKE (target=pgp.services.common:readConfig)
-     `fn0003` MAP
-   `fn0004` MAP
-     `fn0005` MAPINVOKE (target=pgp.services.common:getPackagePath)
-       `fn0006` MAP
-       `fn0007` MAP
-   `fn0008` INVOKE (target=pgp.services.keys:readPrivateKeys)
-     `fn0009` MAP
-     `fn0010` MAP
-   `fn0011` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/registry/getSecKey/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/registry/getSecKey/node.ndf`
- INVOKE `call_3d98a0adeb48fea5` target `pgp.services.common:readConfig`:
  `PGP/ns/pgp/services/registry/getSecKey/flow.xml`:29- MAPINVOKE `call_03e298c99dd41e00` target `pgp.services.common:getPackagePath`:
  `PGP/ns/pgp/services/registry/getSecKey/flow.xml`:161- INVOKE `call_e049b2e3556f0c74` target `pgp.services.keys:readPrivateKeys`:
  `PGP/ns/pgp/services/registry/getSecKey/flow.xml`:221
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.