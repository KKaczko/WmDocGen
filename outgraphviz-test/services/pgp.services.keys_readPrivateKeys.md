# pgp.services.keys:readPrivateKeys

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.keys` |
| Service | `readPrivateKeys` |
| Type | `JAVA` |
| Source service type | `java` |
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


## Java Analysis

### Source Consistency

| Field | Value |
| --- | --- |
| Status | `SOURCE_AND_FRAGMENT_MATCH` |
| Parser mode | `COMPLETE_SOURCE` |
| Fragment kind | `METHOD_BODY` |
| Complete source | `PGP/code/source/pgp/services/keys.java` |
| Fragment | `PGP/ns/pgp/services/keys/readPrivateKeys/java.frag` |
| Class | `keys` |
| Method | `readPrivateKeys` |
| Token match | `True` |
| Method range | `124:2-176:3` |


### Observed Pipeline Reads

| Access | API | Key | Scope | Type | Evidence |
| --- | --- | --- | --- | --- | --- |
| `javapipe_16e5e61a1a9ed03b` | `IDataUtil.getString` | `path` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/keys.java:132` |
| `javapipe_ffbbfc99464e17f2` | `IDataUtil.getString` | `password` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/keys.java:133` |


### Observed Pipeline Writes

| Access | API | Key | Scope | Type | Evidence |
| --- | --- | --- | --- | --- | --- |
| `javapipe_88ad7351c7b94477` | `IDataUtil.put` | `privateKeyRing` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:143` |
| `javapipe_ad3eb3c961975536` | `IDataUtil.put` | `privateKey` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:152` |
| `javapipe_e9caf5b805beeac6` | `IDataUtil.put` | `keyId` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:153` |
| `javapipe_f6cb6d97c845a841` | `IDataUtil.put` | `algorithm` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:154` |
| `javapipe_1a2d1575628c9b25` | `IDataUtil.put` | `format` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:155` |
| `javapipe_c0082c1924c1a7ba` | `IDataUtil.put` | `isSigningKey` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:156` |
| `javapipe_deafaa010cd606d9` | `IDataUtil.put` | `isMasterKey` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:157` |
| `javapipe_15e1d0363349e1fc` | `IDataUtil.put` | `privateKeyData` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/keys.java:171` |


### Observed Pipeline Removes

No Java pipeline accesses were extracted for this section.


### Static Integration Server Calls

No Java Integration Server invocation sites were extracted for this section.


### Dynamic Invocation Sites

No Java Integration Server invocation sites were extracted for this section.


### Declared Imports

| Import | Provenance | Category | Evidence |
| --- | --- | --- | --- |
| `com.softwareag.pgp.PGPInit` | `BOTH` | `PACKAGE_LOCAL_CLASS` | `PGP/code/source/pgp/services/keys.java:35` |
| `com.softwareag.pgp.PGPKeyReader` | `BOTH` | `PACKAGE_LOCAL_CLASS` | `PGP/code/source/pgp/services/keys.java:36` |
| `com.wm.app.b2b.server.Service` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:25` |
| `com.wm.app.b2b.server.ServiceException` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:26` |
| `com.wm.data.*` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:23` |
| `com.wm.data.IData` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:37` |
| `com.wm.data.IDataCursor` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:38` |
| `com.wm.data.IDataFactory` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:39` |
| `com.wm.data.IDataUtil` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:40` |
| `com.wm.util.Values` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:24` |
| `java.util.Iterator` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/keys.java:28` |
| `org.bouncycastle.openpgp.PGPPrivateKey` | `BOTH` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/keys.java:29` |
| `org.bouncycastle.openpgp.PGPPublicKey` | `BOTH` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/keys.java:30` |
| `org.bouncycastle.openpgp.PGPPublicKeyRingCollection` | `BOTH` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/keys.java:31` |
| `org.bouncycastle.openpgp.PGPSecretKey` | `BOTH` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/keys.java:32` |
| `org.bouncycastle.openpgp.PGPSecretKeyRing` | `BOTH` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/keys.java:33` |
| `org.bouncycastle.openpgp.PGPSecretKeyRingCollection` | `BOTH` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/keys.java:34` |


### Referenced Java Types

| Type | Resolved Import | Category | Evidence |
| --- | --- | --- | --- |
| `IData` | `com.wm.data.IData` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:136` |
| `IDataCursor` | `com.wm.data.IDataCursor` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:131` |
| `IDataFactory` | `com.wm.data.IDataFactory` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:136` |
| `IDataUtil` | `com.wm.data.IDataUtil` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:132` |
| `Iterator` | `java.util.Iterator` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/keys.java:145` |
| `PGPInit` | `com.softwareag.pgp.PGPInit` | `PACKAGE_LOCAL_CLASS` | `PGP/code/source/pgp/services/keys.java:150` |
| `PGPKeyReader` | `com.softwareag.pgp.PGPKeyReader` | `PACKAGE_LOCAL_CLASS` | `PGP/code/source/pgp/services/keys.java:142` |
| `PGPPrivateKey` | `org.bouncycastle.openpgp.PGPPrivateKey` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/keys.java:150` |
| `PGPSecretKey` | `org.bouncycastle.openpgp.PGPSecretKey` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/keys.java:148` |
| `PGPSecretKeyRing` | `org.bouncycastle.openpgp.PGPSecretKeyRing` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/keys.java:146` |
| `PGPSecretKeyRingCollection` | `org.bouncycastle.openpgp.PGPSecretKeyRingCollection` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/keys.java:137` |


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
| 1 | True | `FULL` | `pgp.services.registry:getSecKey` | `INVOKES` | `PGP/ns/pgp/services/registry/getSecKey/flow.xml:221` |


## Processes

This service is not part of any declared process.


## Call Occurrences

No static INVOKE call occurrences were extracted.


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

No FLOW tree was extracted.


## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `JAVA_IMPORT_SOURCE_MISMATCH` at `PGP/code/source/pgp/services/keys.java`: Complete-source imports and node.idf import metadata differ.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/keys/readPrivateKeys/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/keys/readPrivateKeys/node.ndf`

## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.