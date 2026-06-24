# pgp.services.decrypt:decryptAndVerify

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.decrypt` |
| Service | `decryptAndVerify` |
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

This service decrypts encrypted data and optionally verifies signatures.

See gcs.pgp.specifications:decryptAndVerifySpec for use of arguments
See gcs.pgp.services.common:getSupportedEncodings for supported character sets

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
| Complete source | `PGP/code/source/pgp/services/decrypt.java` |
| Fragment | `PGP/ns/pgp/services/decrypt/decryptAndVerify/java.frag` |
| Class | `decrypt` |
| Method | `decryptAndVerify` |
| Token match | `True` |
| Method range | `67:2-231:3` |


### Observed Pipeline Reads

| Access | API | Key | Scope | Type | Evidence |
| --- | --- | --- | --- | --- | --- |
| `javapipe_3034f5e45b9cf95d` | `IDataUtil.getString` | `cipherTextPath` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/decrypt.java:75` |
| `javapipe_c2765fa8da0365e5` | `IDataUtil.get` | `cipherTextBytes` | `ROOT_PIPELINE` | `byte[]` | `PGP/code/source/pgp/services/decrypt.java:76` |
| `javapipe_ed6e5ca01a3d76d0` | `IDataUtil.getString` | `cipherTextString` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/decrypt.java:77` |
| `javapipe_a2a55a1a425b1731` | `IDataUtil.get` | `cipherTextStream` | `ROOT_PIPELINE` | `InputStream` | `PGP/code/source/pgp/services/decrypt.java:78` |
| `javapipe_56316e60fb0e8000` | `IDataUtil.getString` | `plainTextEncoding` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/decrypt.java:79` |
| `javapipe_93c7990609a526c3` | `IDataUtil.get` | `publicKeyRingCollection` | `ROOT_PIPELINE` | `PGPPublicKeyRingCollection` | `PGP/code/source/pgp/services/decrypt.java:118` |
| `javapipe_826006c39183ed84` | `IDataUtil.get` | `privateKeyRingCollection` | `ROOT_PIPELINE` | `PGPSecretKeyRingCollection` | `PGP/code/source/pgp/services/decrypt.java:120` |
| `javapipe_e89f3a690d2e5f57` | `IDataUtil.getString` | `privateKeyPassword` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/decrypt.java:122` |
| `javapipe_826695dd03607a3e` | `IDataUtil.getString` | `outputType` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/decrypt.java:132` |
| `javapipe_1401494940baed3e` | `IDataUtil.getString` | `outputPath` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/decrypt.java:133` |


### Observed Pipeline Writes

| Access | API | Key | Scope | Type | Evidence |
| --- | --- | --- | --- | --- | --- |
| `javapipe_8d8aaec91de45ff8` | `IDataUtil.put` | `plainTextPath` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/decrypt.java:191` |
| `javapipe_4ea00d7e447b23e3` | `IDataUtil.put` | `plainTextBytes` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/decrypt.java:199` |
| `javapipe_27b52d8e18ff7324` | `IDataUtil.put` | `plainTextStream` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/decrypt.java:209` |
| `javapipe_2dc4abd8f2a4f9cd` | `IDataUtil.put` | `plainTextString` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/decrypt.java:217` |
| `javapipe_6f58919b7ee4688f` | `IDataUtil.put` | `verified` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/decrypt.java:226` |


### Observed Pipeline Removes

No Java pipeline accesses were extracted for this section.


### Static Integration Server Calls

No Java Integration Server invocation sites were extracted for this section.


### Dynamic Invocation Sites

No Java Integration Server invocation sites were extracted for this section.


### Declared Imports

| Import | Provenance | Category | Evidence |
| --- | --- | --- | --- |
| `com.softwareag.pgp.PGPDecrypt` | `BOTH` | `PACKAGE_LOCAL_CLASS` | `PGP/code/source/pgp/services/decrypt.java:42` |
| `com.wm.app.b2b.server.Service` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/decrypt.java:25` |
| `com.wm.app.b2b.server.ServiceException` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/decrypt.java:43` |
| `com.wm.data.*` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/decrypt.java:23` |
| `com.wm.data.IData` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/decrypt.java:44` |
| `com.wm.data.IDataCursor` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/decrypt.java:45` |
| `com.wm.data.IDataUtil` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/decrypt.java:46` |
| `com.wm.util.Values` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/decrypt.java:24` |
| `java.io.ByteArrayInputStream` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:28` |
| `java.io.ByteArrayOutputStream` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:29` |
| `java.io.File` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:30` |
| `java.io.FileInputStream` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:31` |
| `java.io.FileNotFoundException` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:32` |
| `java.io.FileOutputStream` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:33` |
| `java.io.InputStream` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:35` |
| `java.io.IOException` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:34` |
| `java.io.UnsupportedEncodingException` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:36` |
| `java.nio.charset.Charset` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:37` |
| `java.security.NoSuchProviderException` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:38` |
| `org.bouncycastle.openpgp.PGPException` | `BOTH` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:39` |
| `org.bouncycastle.openpgp.PGPPublicKeyRingCollection` | `BOTH` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:40` |
| `org.bouncycastle.openpgp.PGPSecretKeyRingCollection` | `BOTH` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:41` |


### Referenced Java Types

| Type | Resolved Import | Category | Evidence |
| --- | --- | --- | --- |
| `ByteArrayInputStream` | `java.io.ByteArrayInputStream` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:88` |
| `ByteArrayOutputStream` | `java.io.ByteArrayOutputStream` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:152` |
| `Charset` | `java.nio.charset.Charset` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:113` |
| `File` | `java.io.File` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:85` |
| `FileInputStream` | `java.io.FileInputStream` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:85` |
| `FileNotFoundException` | `java.io.FileNotFoundException` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:98` |
| `FileOutputStream` | `java.io.FileOutputStream` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:185` |
| `IDataCursor` | `com.wm.data.IDataCursor` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/decrypt.java:74` |
| `IDataUtil` | `com.wm.data.IDataUtil` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/decrypt.java:75` |
| `InputStream` | `java.io.InputStream` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:78` |
| `IOException` | `java.io.IOException` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:104` |
| `NoSuchProviderException` | `java.security.NoSuchProviderException` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:173` |
| `PGPDecrypt` | `com.softwareag.pgp.PGPDecrypt` | `PACKAGE_LOCAL_CLASS` | `PGP/code/source/pgp/services/decrypt.java:158` |
| `PGPException` | `org.bouncycastle.openpgp.PGPException` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:170` |
| `PGPPublicKeyRingCollection` | `org.bouncycastle.openpgp.PGPPublicKeyRingCollection` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:118` |
| `PGPSecretKeyRingCollection` | `org.bouncycastle.openpgp.PGPSecretKeyRingCollection` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:120` |
| `ServiceException` | `com.wm.app.b2b.server.ServiceException` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/decrypt.java:99` |
| `UnsupportedEncodingException` | `java.io.UnsupportedEncodingException` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/decrypt.java:101` |


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
| 1 | True | `FULL` | `pgp.services.decrypt:decryptAndVerifyFile` | `INVOKES` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyFile/flow.xml:630` |
| 1 | True | `FULL` | `pgp.services.decrypt:decryptAndVerifyString` | `INVOKES` | `PGP/ns/pgp/services/decrypt/decryptAndVerifyString/flow.xml:630` |
| 1 | True | `FULL` | `pgp.services.decrypt:decryptFile` | `INVOKES` | `PGP/ns/pgp/services/decrypt/decryptFile/flow.xml:33` |
| 1 | True | `FULL` | `pgp.services.decrypt:decryptString` | `INVOKES` | `PGP/ns/pgp/services/decrypt/decryptString/flow.xml:33` |


## Processes

This service is not part of any declared process.


## Call Occurrences

No static INVOKE call occurrences were extracted.


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

No FLOW tree was extracted.


## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `JAVA_IMPORT_SOURCE_MISMATCH` at `PGP/code/source/pgp/services/decrypt.java`: Complete-source imports and node.idf import metadata differ.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/decrypt/decryptAndVerify/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/decrypt/decryptAndVerify/node.ndf`

## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.