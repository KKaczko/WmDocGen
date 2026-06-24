# pgp.documents:SecKeyRegEntry

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.documents` |
| Document | `SecKeyRegEntry` |
| Basis | `CONFIRMED` |
| Declared package | `PGP` |

## Description

No description was declared in supported metadata.

## Field Hierarchy

| Field | Type | Dimension | Optional | Document Reference | Source |
| --- | --- | --- | --- | --- | --- |
| `keyRegData` | `recref` | `0` / `SCALAR` |  | `pgp.documents:KeyRegData` | `PGP/ns/pgp/documents/SecKeyRegEntry/node.ndf:18` |
| `PrivateKeyData` | `recref` | `0` / `SCALAR` |  | `pgp.documents:PrivateKeyData` | `PGP/ns/pgp/documents/SecKeyRegEntry/node.ndf:38` |


## Document References

| Document | Resolved | Occurrences |
| --- | --- | ---: |
| `pgp.documents:KeyRegData` | True | 1 |
| `pgp.documents:PrivateKeyData` | True | 1 |


## Referenced By Services

| Service | Usage | Resolved | Occurrences |
| --- | --- | --- | ---: |
| `pgp.services.registry:getSecKey` | `OUTPUT` | True | 1 |


## Referenced By Processes

No process-document relationships were derived for this document.


## Referenced By Documents

No document dependencies were extracted.


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

- Document metadata: `PGP/ns/pgp/documents/SecKeyRegEntry/node.ndf`:4

## Analysis Limitations

M3 extracts technical Document Type structure and document-reference evidence. It does not validate mapping paths against schemas, infer business meaning, or expand referenced documents recursively.
