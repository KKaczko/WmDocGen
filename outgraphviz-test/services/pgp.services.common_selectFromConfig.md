# pgp.services.common:selectFromConfig

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.common` |
| Service | `selectFromConfig` |
| Type | `JAVA` |
| Source service type | `java` |
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
| `config` | `recref` | 0 |  | `pgp.documents.config:PGPconfig` |
| `userId` | `string` | 0 |  | `` |


## Output Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `key` | `recref` | 0 |  | `pgp.documents.config:KeyConfig` |


## Document Type Usage

### Input Document Types

| Usage | Resolved | Document | Occurrences |
| --- | --- | --- | ---: |
| `INPUT` | True | [`pgp.documents.config:PGPconfig`](../documents/pgp.documents.config_PGPconfig.md) | 1 |


### Output Document Types

| Usage | Resolved | Document | Occurrences |
| --- | --- | --- | ---: |
| `OUTPUT` | True | [`pgp.documents.config:KeyConfig`](../documents/pgp.documents.config_KeyConfig.md) | 1 |


### Resolved Document References

| Usage | Field | Resolved | Target | Source |
| --- | --- | --- | --- | --- |
| `INPUT` | `config` | True | [`pgp.documents.config:PGPconfig`](../documents/pgp.documents.config_PGPconfig.md) | `PGP/ns/pgp/services/common/selectFromConfig/node.ndf:19` |
| `OUTPUT` | `key` | True | [`pgp.documents.config:KeyConfig`](../documents/pgp.documents.config_KeyConfig.md) | `PGP/ns/pgp/services/common/selectFromConfig/node.ndf:72` |


### Unresolved Document References

No document reference occurrences were extracted for this section.


## Java Analysis

### Source Consistency

| Field | Value |
| --- | --- |
| Status | `SOURCE_AND_FRAGMENT_MATCH` |
| Parser mode | `COMPLETE_SOURCE` |
| Fragment kind | `METHOD_BODY` |
| Complete source | `PGP/code/source/pgp/services/common.java` |
| Fragment | `PGP/ns/pgp/services/common/selectFromConfig/java.frag` |
| Class | `common` |
| Method | `selectFromConfig` |
| Token match | `True` |
| Method range | `180:2-234:3` |


### Observed Pipeline Reads

| Access | API | Key | Scope | Type | Evidence |
| --- | --- | --- | --- | --- | --- |
| `javapipe_acc77798afa14a07` | `IDataUtil.getString` | `userId` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/common.java:192` |
| `javapipe_264589b64de7e920` | `IDataUtil.getIData` | `config` | `ROOT_PIPELINE` | `IData` | `PGP/code/source/pgp/services/common.java:193` |
| `javapipe_4e654f25b9a61086` | `IDataUtil.getIData` | `keys` | `NESTED_IDATA` | `IData` | `PGP/code/source/pgp/services/common.java:199` |
| `javapipe_af94b3e79f99bebb` | `IDataUtil.getIDataArray` | `key` | `NESTED_IDATA` | `IData[]` | `PGP/code/source/pgp/services/common.java:203` |
| `javapipe_a20e22a04ad9256f` | `IDataUtil.getString` | `@userId` | `NESTED_IDATA` | `String` | `PGP/code/source/pgp/services/common.java:209` |


### Observed Pipeline Writes

| Access | API | Key | Scope | Type | Evidence |
| --- | --- | --- | --- | --- | --- |
| `javapipe_9c81d5830fc24fc8` | `IDataUtil.put` | `key` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/common.java:226` |


### Observed Pipeline Removes

No Java pipeline accesses were extracted for this section.


### Static Integration Server Calls

No Java Integration Server invocation sites were extracted for this section.


### Dynamic Invocation Sites

No Java Integration Server invocation sites were extracted for this section.


### Declared Imports

| Import | Provenance | Category | Evidence |
| --- | --- | --- | --- |
| `com.wm.app.b2b.server.Server` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:34` |
| `com.wm.app.b2b.server.Service` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:25` |
| `com.wm.app.b2b.server.ServiceException` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:26` |
| `com.wm.data.*` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:23` |
| `com.wm.data.IData` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:35` |
| `com.wm.data.IDataCursor` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:36` |
| `com.wm.data.IDataUtil` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:37` |
| `com.wm.util.Values` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:24` |
| `java.io.ByteArrayOutputStream` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/common.java:28` |
| `java.io.File` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/common.java:29` |
| `java.io.FileInputStream` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/common.java:30` |
| `java.nio.charset.Charset` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/common.java:31` |
| `java.util.HashMap` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/common.java:32` |
| `java.util.Map` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/common.java:33` |


### Referenced Java Types

| Type | Resolved Import | Category | Evidence |
| --- | --- | --- | --- |
| `HashMap` | `java.util.HashMap` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/common.java:186` |
| `IData` | `com.wm.data.IData` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:186` |
| `IDataCursor` | `com.wm.data.IDataCursor` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:189` |
| `IDataUtil` | `com.wm.data.IDataUtil` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:192` |
| `Map` | `java.util.Map` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/common.java:186` |


## FLOW Overview

| Metric | Count |
| --- | ---: |
| Sequences | 0 |
| Branches | 0 |
| Loops | 0 |
| Exits | 0 |
| Call occurrences | 0 |
| Unique dependencies | 0 |

## Mapping Overview

| Metric | Count |
| --- | ---: |
| Flow maps | 0 |
| Copy operations | 0 |
| Set operations | 0 |
| Delete operations | 0 |
| Transformer bindings | 0 |
| Transformer input bindings | 0 |
| Transformer output bindings | 0 |
| Partially interpreted mappings | 0 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

No COPY mapping operations were extracted.


## Mapping Sets

No SET mapping operations were extracted.


## Mapping Deletes

No DELETE mapping operations were extracted.


## Transformer Bindings

No MAPINVOKE transformer bindings were extracted.


## Normal Service Dependencies

No static targets were extracted for this dependency kind.


## Transformer Dependencies

No static targets were extracted for this dependency kind.


## Called By

| Occurrences | Resolved | Target Support | Source | Kind | Source sample |
| ---: | --- | --- | --- | --- | --- |
| 1 | True | `FULL` | `pgp.services.common:readConfig` | `INVOKES` | `PGP/ns/pgp/services/common/readConfig/flow.xml:1297` |


## Processes

This service is not part of any declared process.


## Call Occurrences

No static INVOKE call occurrences were extracted.


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

No FLOW tree was extracted.


## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `JAVA_IMPORT_SOURCE_MISMATCH` at `PGP/code/source/pgp/services/common.java`: Complete-source imports and node.idf import metadata differ.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/common/selectFromConfig/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/common/selectFromConfig/node.ndf`

## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.