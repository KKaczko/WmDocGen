# pgp.services.keys:readPublicKeys

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.keys` |
| Service | `readPublicKeys` |
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

This service reads an ASCII-armored public key file.

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
| Complete source | `PGP/code/source/pgp/services/keys.java` |
| Fragment | `PGP/ns/pgp/services/keys/readPublicKeys/java.frag` |
| Class | `keys` |
| Method | `readPublicKeys` |
| Token match | `True` |
| Method range | `182:2-225:3` |


### Observed Pipeline Reads

| Access | API | Key | Scope | Type | Evidence |
| --- | --- | --- | --- | --- | --- |
| `javapipe_1a1f9aff5e0a0868` | `IDataUtil.getString` | `path` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/keys.java:189` |
| `javapipe_a3ba4dbad14a7dba` | `IDataUtil.getString` | `keyExchangeAlgorithm` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/keys.java:190` |


### Observed Pipeline Writes

| Access | API | Key | Scope | Type | Evidence |
| --- | --- | --- | --- | --- | --- |
| `javapipe_96689e250a9004c7` | `IDataUtil.put` | `publicKeyRing` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:200` |
| `javapipe_d9efa785b03eaeaf` | `IDataUtil.put` | `publicKey` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:204` |
| `javapipe_1cfc45acd637d76f` | `IDataUtil.put` | `keyId` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:205` |
| `javapipe_54850dec117fb859` | `IDataUtil.put` | `algorithm` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:206` |
| `javapipe_50586a73ecc6c0d4` | `IDataUtil.put` | `bitStrength` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:207` |
| `javapipe_c8358341a35f4f71` | `IDataUtil.put` | `isEncryptionKey` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:208` |
| `javapipe_e4bf1c49fdf85e7d` | `IDataUtil.put` | `isMasterKey` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:209` |
| `javapipe_7e1fb9ea09fcdccf` | `IDataUtil.put` | `isRevoked` | `NESTED_IDATA` | `` | `PGP/code/source/pgp/services/keys.java:210` |
| `javapipe_d7f1c2123d2934e6` | `IDataUtil.put` | `publicKeyData` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/keys.java:219` |


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
| `IData` | `com.wm.data.IData` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:194` |
| `IDataCursor` | `com.wm.data.IDataCursor` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:188` |
| `IDataFactory` | `com.wm.data.IDataFactory` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:194` |
| `IDataUtil` | `com.wm.data.IDataUtil` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:189` |
| `PGPInit` | `com.softwareag.pgp.PGPInit` | `PACKAGE_LOCAL_CLASS` | `PGP/code/source/pgp/services/keys.java:203` |
| `PGPKeyReader` | `com.softwareag.pgp.PGPKeyReader` | `PACKAGE_LOCAL_CLASS` | `PGP/code/source/pgp/services/keys.java:199` |
| `PGPPublicKey` | `org.bouncycastle.openpgp.PGPPublicKey` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/keys.java:196` |
| `PGPPublicKeyRingCollection` | `org.bouncycastle.openpgp.PGPPublicKeyRingCollection` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/keys.java:195` |
| `ServiceException` | `com.wm.app.b2b.server.ServiceException` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/keys.java:214` |


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
| 1 | True | `FULL` | `pgp.services.registry:getPubKey` | `INVOKES` | `PGP/ns/pgp/services/registry/getPubKey/flow.xml:277` |


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

- Service metadata: `PGP/ns/pgp/services/keys/readPublicKeys/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/keys/readPublicKeys/node.ndf`

## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.