# pgp.documents:PrivateKeyData

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.documents` |
| Document | `PrivateKeyData` |
| Basis | `CONFIRMED` |
| Declared package | `GCS_PGP` |

## Description

No description was declared in supported metadata.

## Field Hierarchy

| Field | Type | Dimension | Optional | Document Reference | Source |
| --- | --- | --- | --- | --- | --- |
| `privateKeyRing` | `object` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PrivateKeyData/node.ndf:14` |
| `privateKey` | `object` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PrivateKeyData/node.ndf:28` |
| `keyId` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PrivateKeyData/node.ndf:42` |
| `algorithm` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PrivateKeyData/node.ndf:68` |
| `format` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PrivateKeyData/node.ndf:94` |
| `isSigningKey` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PrivateKeyData/node.ndf:120` |
| `isMasterKey` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PrivateKeyData/node.ndf:146` |


## Document References

No document dependencies were extracted.


## Referenced By Services

No service-document dependencies were extracted.


## Referenced By Processes

No process-document relationships were derived for this document.


## Referenced By Documents

| Document | Resolved | Occurrences |
| --- | --- | ---: |
| `pgp.documents:SecKeyRegEntry` | True | 1 |


## Unresolved References

No unresolved document references were extracted for this document.


## Disclosure Policies

- Free text mode: include
- Literal mode: redact
- Secret guard: enabled
- Secret guard strategy: secret-guard.v1


## Findings

No document-level findings.


## Source Evidence

- Document metadata: `PGP/ns/pgp/documents/PrivateKeyData/node.ndf`:4

## Analysis Limitations

M3 extracts technical Document Type structure and document-reference evidence. It does not validate mapping paths against schemas, infer business meaning, or expand referenced documents recursively.
