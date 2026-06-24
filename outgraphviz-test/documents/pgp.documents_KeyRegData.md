# pgp.documents:KeyRegData

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.documents` |
| Document | `KeyRegData` |
| Basis | `CONFIRMED` |
| Declared package | `WxPGP` |

## Description

No description was declared in supported metadata.

## Field Hierarchy

| Field | Type | Dimension | Optional | Document Reference | Source |
| --- | --- | --- | --- | --- | --- |
| `@UserId` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/KeyRegData/node.ndf:18` |
| `KeyPath` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/KeyRegData/node.ndf:37` |
| `keyExchangeAlgorithm` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/KeyRegData/node.ndf:56` |
| `secret` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/KeyRegData/node.ndf:75` |


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

- Document metadata: `PGP/ns/pgp/documents/KeyRegData/node.ndf`:4

## Analysis Limitations

M3 extracts technical Document Type structure and document-reference evidence. It does not validate mapping paths against schemas, infer business meaning, or expand referenced documents recursively.
