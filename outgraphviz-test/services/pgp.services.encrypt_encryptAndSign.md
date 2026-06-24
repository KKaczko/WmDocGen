# pgp.services.encrypt:encryptAndSign

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.services.encrypt` |
| Service | `encryptAndSign` |
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

This service encrypts and optionally signs plain text data.

See gcs.pgp.specifications:encryptAndSignSpec for use of arguments
See gcs.pgp.services.common:getSupportedEncodings for supported character sets
See gcs.pgp.services.keys:listEncryptionAlgorithms for supported encryption algorithms
See gcs.pgp.services.keys:listKeyExchangeAlgorithms for supported key exchange algorithms

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
| Complete source | `PGP/code/source/pgp/services/encrypt.java` |
| Fragment | `PGP/ns/pgp/services/encrypt/encryptAndSign/java.frag` |
| Class | `encrypt` |
| Method | `encryptAndSign` |
| Token match | `True` |
| Method range | `69:2-240:3` |


### Observed Pipeline Reads

| Access | API | Key | Scope | Type | Evidence |
| --- | --- | --- | --- | --- | --- |
| `javapipe_8df52a90ff4e7007` | `IDataUtil.getString` | `plainTextPath` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/encrypt.java:76` |
| `javapipe_8cd5147752dfd315` | `IDataUtil.get` | `plainTextBytes` | `ROOT_PIPELINE` | `byte[]` | `PGP/code/source/pgp/services/encrypt.java:77` |
| `javapipe_f91e59b48c53c538` | `IDataUtil.getString` | `plainTextString` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/encrypt.java:78` |
| `javapipe_fa57d68c720c35ac` | `IDataUtil.get` | `plainTextStream` | `ROOT_PIPELINE` | `InputStream` | `PGP/code/source/pgp/services/encrypt.java:79` |
| `javapipe_909412fbb209192d` | `IDataUtil.getString` | `plainTextEncoding` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/encrypt.java:80` |
| `javapipe_058762f29371fae8` | `IDataUtil.get` | `publicKey` | `ROOT_PIPELINE` | `PGPPublicKey` | `PGP/code/source/pgp/services/encrypt.java:115` |
| `javapipe_19878ddfe23cd2da` | `IDataUtil.getString` | `encryptionAlgorithm` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/encrypt.java:116` |
| `javapipe_5cb7d5cb1b00e452` | `IDataUtil.get` | `privateKey` | `ROOT_PIPELINE` | `PGPPrivateKey` | `PGP/code/source/pgp/services/encrypt.java:117` |
| `javapipe_7d4aa348cc62685f` | `IDataUtil.getString` | `privateKeyPassword` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/encrypt.java:118` |
| `javapipe_1dbc7bc624dcd11b` | `IDataUtil.getString` | `signingAlgorithm` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/encrypt.java:119` |
| `javapipe_6261c5f7a8e470ad` | `IDataUtil.getString` | `outputType` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/encrypt.java:129` |
| `javapipe_4ac969f0ce480491` | `IDataUtil.getString` | `outputPath` | `ROOT_PIPELINE` | `String` | `PGP/code/source/pgp/services/encrypt.java:130` |


### Observed Pipeline Writes

| Access | API | Key | Scope | Type | Evidence |
| --- | --- | --- | --- | --- | --- |
| `javapipe_1aa137d38e0d6f1d` | `IDataUtil.put` | `cipherTextPath` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/encrypt.java:199` |
| `javapipe_a73738d7e96b9dfd` | `IDataUtil.put` | `cipherTextBytes` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/encrypt.java:207` |
| `javapipe_f6fd4c34a7784f06` | `IDataUtil.put` | `cipherTextStream` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/encrypt.java:217` |
| `javapipe_f23ef2c779dde27a` | `IDataUtil.put` | `cipherTextString` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/encrypt.java:225` |
| `javapipe_89f0185cce4c1864` | `IDataUtil.put` | `signed` | `ROOT_PIPELINE` | `` | `PGP/code/source/pgp/services/encrypt.java:234` |


### Observed Pipeline Removes

No Java pipeline accesses were extracted for this section.


### Static Integration Server Calls

No Java Integration Server invocation sites were extracted for this section.


### Dynamic Invocation Sites

No Java Integration Server invocation sites were extracted for this section.


### Declared Imports

| Import | Provenance | Category | Evidence |
| --- | --- | --- | --- |
| `com.softwareag.pgp.PGPEncrypt` | `BOTH` | `PACKAGE_LOCAL_CLASS` | `PGP/code/source/pgp/services/encrypt.java:28` |
| `com.softwareag.pgp.PGPInit` | `BOTH` | `PACKAGE_LOCAL_CLASS` | `PGP/code/source/pgp/services/encrypt.java:29` |
| `com.wm.app.b2b.server.Service` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/encrypt.java:25` |
| `com.wm.app.b2b.server.ServiceException` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/encrypt.java:26` |
| `com.wm.data.*` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/encrypt.java:23` |
| `com.wm.data.IData` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/encrypt.java:46` |
| `com.wm.data.IDataCursor` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/encrypt.java:47` |
| `com.wm.data.IDataUtil` | `BOTH` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/encrypt.java:48` |
| `com.wm.util.Values` | `COMPLETE_SOURCE` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/encrypt.java:24` |
| `java.io.ByteArrayInputStream` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:30` |
| `java.io.ByteArrayOutputStream` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:31` |
| `java.io.File` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:32` |
| `java.io.FileInputStream` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:33` |
| `java.io.FileNotFoundException` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:34` |
| `java.io.FileOutputStream` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:35` |
| `java.io.InputStream` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:37` |
| `java.io.IOException` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:36` |
| `java.io.UnsupportedEncodingException` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:38` |
| `java.nio.charset.Charset` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:39` |
| `java.security.NoSuchAlgorithmException` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:40` |
| `java.security.NoSuchProviderException` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:41` |
| `java.security.SignatureException` | `BOTH` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:42` |
| `org.bouncycastle.openpgp.PGPException` | `BOTH` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:43` |
| `org.bouncycastle.openpgp.PGPPrivateKey` | `BOTH` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:44` |
| `org.bouncycastle.openpgp.PGPPublicKey` | `BOTH` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:45` |


### Referenced Java Types

| Type | Resolved Import | Category | Evidence |
| --- | --- | --- | --- |
| `ByteArrayInputStream` | `java.io.ByteArrayInputStream` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:89` |
| `ByteArrayOutputStream` | `java.io.ByteArrayOutputStream` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:149` |
| `Charset` | `java.nio.charset.Charset` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:110` |
| `File` | `java.io.File` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:86` |
| `FileInputStream` | `java.io.FileInputStream` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:86` |
| `FileNotFoundException` | `java.io.FileNotFoundException` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:99` |
| `FileOutputStream` | `java.io.FileOutputStream` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:193` |
| `IDataCursor` | `com.wm.data.IDataCursor` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/encrypt.java:75` |
| `IDataUtil` | `com.wm.data.IDataUtil` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/encrypt.java:76` |
| `InputStream` | `java.io.InputStream` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:79` |
| `IOException` | `java.io.IOException` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:103` |
| `NoSuchAlgorithmException` | `java.security.NoSuchAlgorithmException` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:178` |
| `NoSuchProviderException` | `java.security.NoSuchProviderException` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:175` |
| `PGPEncrypt` | `com.softwareag.pgp.PGPEncrypt` | `PACKAGE_LOCAL_CLASS` | `PGP/code/source/pgp/services/encrypt.java:155` |
| `PGPException` | `org.bouncycastle.openpgp.PGPException` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:170` |
| `PGPInit` | `com.softwareag.pgp.PGPInit` | `PACKAGE_LOCAL_CLASS` | `PGP/code/source/pgp/services/encrypt.java:156` |
| `PGPPrivateKey` | `org.bouncycastle.openpgp.PGPPrivateKey` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:117` |
| `PGPPublicKey` | `org.bouncycastle.openpgp.PGPPublicKey` | `THIRD_PARTY_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:115` |
| `ServiceException` | `com.wm.app.b2b.server.ServiceException` | `WEBMETHODS_API` | `PGP/code/source/pgp/services/encrypt.java:100` |
| `SignatureException` | `java.security.SignatureException` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:181` |
| `UnsupportedEncodingException` | `java.io.UnsupportedEncodingException` | `JAVA_STANDARD_LIBRARY` | `PGP/code/source/pgp/services/encrypt.java:101` |


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
| 1 | True | `FULL` | `pgp.services.encrypt:encryptAndSignFile` | `INVOKES` | `PGP/ns/pgp/services/encrypt/encryptAndSignFile/flow.xml:947` |
| 1 | True | `FULL` | `pgp.services.encrypt:encryptAndSignString` | `INVOKES` | `PGP/ns/pgp/services/encrypt/encryptAndSignString/flow.xml:898` |
| 1 | True | `FULL` | `pgp.services.encrypt:encryptFile` | `INVOKES` | `PGP/ns/pgp/services/encrypt/encryptFile/flow.xml:157` |
| 1 | True | `FULL` | `pgp.services.encrypt:encryptString` | `INVOKES` | `PGP/ns/pgp/services/encrypt/encryptString/flow.xml:168` |


## Processes

This service is not part of any declared process.


## Call Occurrences

No static INVOKE call occurrences were extracted.


## Transformer Call Occurrences

No static MAPINVOKE call occurrences were extracted.


## FLOW Outline

No FLOW tree was extracted.


## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `JAVA_IMPORT_SOURCE_MISMATCH` at `PGP/code/source/pgp/services/encrypt.java`: Complete-source imports and node.idf import metadata differ.

## Source Evidence

- Service metadata: `PGP/ns/pgp/services/encrypt/encryptAndSign/node.ndf`
- Signature metadata: `PGP/ns/pgp/services/encrypt/encryptAndSign/node.ndf`

## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.