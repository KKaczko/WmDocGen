# pgp.services.registry:getPubKey

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.registry` |
| Service | `getPubKey` |
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
| `keyRegEntry` | `recref` | 0 |  | `pgp.documents:PubKeyRegEntry` |


## Document Type Usage

### Input Document Types

No document dependencies were extracted for this usage role.


### Output Document Types

| Usage | Resolved | Document | Occurrences |
| --- | --- | --- | ---: |
| `OUTPUT` | True | [`pgp.documents:PubKeyRegEntry`](../documents/pgp.documents_PubKeyRegEntry.md) | 1 |


### Resolved Document References

| Usage | Field | Resolved | Target | Source |
| --- | --- | --- | --- | --- |
| `OUTPUT` | `keyRegEntry` | True | [`pgp.documents:PubKeyRegEntry`](../documents/pgp.documents_PubKeyRegEntry.md) | `PGP/ns/pgp/services/registry/getPubKey/node.ndf:52` |


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
| Flow maps | 8 |
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
| `mapop_400470d79bcc849a` | `/key;4;0;wx.pgp.documents.config:KeyConfig/pub;2;0/filename;1;0` | `/fileName;1;0` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:263` |
| `mapop_c8bd83dd0fe408bd` | `/path;1;0` | `/path;1;0` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:271` |
| `mapop_dc31382d3faadede` | `/key;4;0;wx.pgp.documents:KeyConfig/pub;2;0/exchangeAlgorithm;1;0` | `/keyExchangeAlgorithm;1;0` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:384` |
| `mapop_d3d11d25a92e3fab` | `/publicKeyData;4;0;pgp.documents:PublicKeyData` | `/keyRegEntry;4;0;pgp.documents:PubKeyRegEntry/PublicKeyData;4;0;pgp.documents:PublicKeyData` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:656` |
| `mapop_08669f64e79861fc` | `/key;4;0;pgp.documents.config:KeyConfig/@userId;1;0` | `/keyRegEntry;4;0;pgp.documents:PubKeyRegEntry/keyRegData;4;0;pgp.documents:KeyRegData/@UserId;1;0` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:659` |
| `mapop_87a42afe355cb72c` | `/path;1;0` | `/keyRegEntry;4;0;pgp.documents:PubKeyRegEntry/keyRegData;4;0;pgp.documents:KeyRegData/KeyPath;1;0` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:662` |
| `mapop_3a6bb3cc859953c5` | `/key;4;0;pgp.documents.config:KeyConfig/pub;2;0/exchangeAlgorithm;1;0` | `/keyRegEntry;4;0;pgp.documents:PubKeyRegEntry/keyRegData;4;0;pgp.documents:KeyRegData/keyExchangeAlgorithm;1;0` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:665` |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_c227a6aa7ce1d656` |  | `/subDir;1;0` | `<redacted:literal>` | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:225` |


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_51cd46ecc26ff5ba` | `/userId;1;0` | `/userId;1;0` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:118` |
| `mapop_cf522410ba804e44` | `/keyExchangeAlgorithm;1;0` | `/keyExchangeAlgorithm;1;0` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:492` |
| `mapop_b275f47095891873` | `/publicKeyData;4;0;pgp.documents:PublicKeyData` | `/publicKeyData;4;0;pgp.documents:PublicKeyData` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:668` |
| `mapop_ef23d9e241d5b500` | `/path;1;0` | `/path;1;0` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:671` |
| `mapop_593ed49b8a2906a1` | `/key;4;0;pgp.documents.config:KeyConfig` | `/key;4;0;pgp.documents.config:KeyConfig` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:674` |


## Transformer Bindings

| Binding | Direction | Transformer | Pipeline | Literal | Evidence |
| --- | --- | --- | --- | --- | --- |
| `bind_00779e637b50192e` | `INTO_TRANSFORMER` | `/subDir;1;0` |  | `<redacted:literal>` | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:225` |
| `bind_3d75340c2f73306e` | `INTO_TRANSFORMER` | `/fileName;1;0` | `/key;4;0;wx.pgp.documents.config:KeyConfig/pub;2;0/filename;1;0` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:263` |
| `bind_935d2406a3f39d73` | `FROM_TRANSFORMER` | `/path;1;0` | `/path;1;0` |  | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:271` |


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `FLOW` | `FULL` | `pgp.services.common:readConfig` |
| 1 | True | `JAVA` | `FULL` | `pgp.services.keys:readPublicKeys` |


## Transformer Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` |


## Called By

| Occurrences | Resolved | Target Support | Source | Kind | Source sample |
| ---: | --- | --- | --- | --- | --- |
| 1 | True | `FULL` | `pgp.services.decrypt:decryptAndVerifyFile` | `INVOKES` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:316` |
| 1 | True | `FULL` | `pgp.services.decrypt:decryptAndVerifyString` | `INVOKES` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:316` |
| 1 | True | `FULL` | `pgp.services.encrypt:encryptAndSignFile` | `INVOKES` | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:29` |
| 1 | True | `FULL` | `pgp.services.encrypt:encryptAndSignString` | `INVOKES` | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:29` |
| 1 | True | `FULL` | `pgp.services.encrypt:encryptFile` | `INVOKES` | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:29` |
| 1 | True | `FULL` | `pgp.services.encrypt:encryptString` | `INVOKES` | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:29` |
| 1 | True | `FULL` | `pgp.test.keys:testReadPublicKeys` | `INVOKES` | `PGP/ns/pgp/test/keys/testReadPublicKeys/flow.xml:39` |


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_0262a9ae6a24f694` | True | `FLOW` | `FULL` | `pgp.services.common:readConfig` | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:29` |
| `call_223f935df2c33c43` | True | `JAVA` | `FULL` | `pgp.services.keys:readPublicKeys` | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:277` |


## Transformer Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_9c3833b8d478890f` | True | `JAVA` | `FULL` | `pgp.services.common:getPackagePath` | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:217` |


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` INVOKE (target=pgp.services.common:readConfig)
-     `fn0003` MAP
-     `fn0004` MAP
-   `fn0005` MAP
-     `fn0006` MAPINVOKE (target=pgp.services.common:getPackagePath)
-       `fn0007` MAP
-       `fn0008` MAP
-   `fn0009` INVOKE (target=pgp.services.keys:readPublicKeys)
-     `fn0010` MAP
-     `fn0011` MAP
-   `fn0012` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/registry/getPubKey/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/registry/getPubKey/node.ndf`
- INVOKE `call_0262a9ae6a24f694` target `pgp.services.common:readConfig`:
  `PGP/ns/pgp/services/registry/getPubKey/flow.xml`:29- MAPINVOKE `call_9c3833b8d478890f` target `pgp.services.common:getPackagePath`:
  `PGP/ns/pgp/services/registry/getPubKey/flow.xml`:217- INVOKE `call_223f935df2c33c43` target `pgp.services.keys:readPublicKeys`:
  `PGP/ns/pgp/services/registry/getPubKey/flow.xml`:277
## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.