# pgp.services.common:getFileContent

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.common` |
| Service | `getFileContent` |
| Type | `JAVA` |
| Source service type | `java` |
| Analysis support | `FULL` |
| Description status | `SOURCE_DESCRIPTION` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

## Analysis Support

The artifact was analyzed by the supported parser for its service type.

## Description

Extracted description:

This service reads the content of a text file

28-Mar-2011 :: Christian Schuit, Software AG :: Created

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


## Java Analysis

### Source Consistency

| Field | Value |
| --- | --- |
| Status | `SOURCE_AND_FRAGMENT_MATCH` |
| Parser mode | `COMPLETE_SOURCE` |
| Fragment kind | `METHOD_BODY` |
| Complete source | `PGP/code/source/pgp/services/common.java` |
| Fragment | `PGP/ns/pgp/services/common/getFileContent/java.frag` |
| Class | `common` |
| Method | `getFileContent` |
| Token match | `True` |
| Method range | `58:2-105:3` |


### Observed Pipeline Reads

| Access | API | Key | Scope | Type | Evidence |
| --- | --- | --- | --- | --- | --- |
| `javapipe_35cf1c87dc6fa6bb` | `IDataUtil.getString` | `path` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/common.java:66` |
| `javapipe_ef7eca8ce1bc81ff` | `IDataUtil.getString` | `encoding` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/common.java:67` |


### Observed Pipeline Writes

| Access | API | Key | Scope | Type | Evidence |
| --- | --- | --- | --- | --- | --- |
| `javapipe_fb8ae0da3d73d7da` | `IDataUtil.put` | `content` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/common.java:91` |


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
| `ByteArrayOutputStream` | `java.io.ByteArrayOutputStream` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/common.java:81` |
| `Charset` | `java.nio.charset.Charset` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/common.java:75` |
| `File` | `java.io.File` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/common.java:83` |
| `FileInputStream` | `java.io.FileInputStream` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/common.java:80` |
| `IDataCursor` | `com.wm.data.IDataCursor` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:65` |
| `IDataUtil` | `com.wm.data.IDataUtil` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:66` |
| `ServiceException` | `com.wm.app.b2b.server.ServiceException` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/common.java:71` |


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

No incoming static service calls target this service.


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

- Service metadata: `PGP/ns/pgp/services/common/getFileContent/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/common/getFileContent/node.ndf`

## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.