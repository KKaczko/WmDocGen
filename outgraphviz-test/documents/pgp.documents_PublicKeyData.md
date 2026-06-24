# pgp.documents:PublicKeyData

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.documents` |
| Document | `PublicKeyData` |
| Basis | `CONFIRMED` |
| Declared package | `GCS_PGP` |

## Description

No description was declared in supported metadata.

## Field Hierarchy

| Field | Type | Dimension | Optional | Document Reference | Source |
| --- | --- | --- | --- | --- | --- |
| `publicKeyRing` | `object` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PublicKeyData/node.ndf:14` |
| `publicKey` | `object` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PublicKeyData/node.ndf:28` |
| `keyId` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PublicKeyData/node.ndf:42` |
| `algorithm` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PublicKeyData/node.ndf:68` |
| `bitStrength` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PublicKeyData/node.ndf:94` |
| `isEncryptionKey` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PublicKeyData/node.ndf:120` |
| `isMasterKey` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PublicKeyData/node.ndf:146` |
| `isRevoked` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/PublicKeyData/node.ndf:172` |


## Document References

No document dependencies were extracted.


## Referenced By Services

No service-document dependencies were extracted.


## Referenced By Processes

No process-document relationships were derived for this document.


## Referenced By Documents

| Document | Resolved | Occurrences |
| --- | --- | ---: |
| `pgp.documents:PubKeyRegEntry` | True | 1 |


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

- Document metadata: `PGP/ns/pgp/documents/PublicKeyData/node.ndf`:4

## Analysis Limitations

M3 extracts technical Document Type structure and document-reference evidence. It does not validate mapping paths against schemas, infer business meaning, or expand referenced documents recursively.
