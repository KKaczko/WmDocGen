# pgp.documents.config:KeyConfig

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.documents.config` |
| Document | `KeyConfig` |
| Basis | `CONFIRMED` |
| Declared package | `PGP` |

## Description

No description was declared in supported metadata.

## Field Hierarchy

| Field | Type | Dimension | Optional | Document Reference | Source |
| --- | --- | --- | --- | --- | --- |
| `@userId` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/config/KeyConfig/node.ndf:18` |
| `pub` | `record` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/config/KeyConfig/node.ndf:37` |
| `  filename` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/config/KeyConfig/node.ndf:54` |
| `  exchangeAlgorithm` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/config/KeyConfig/node.ndf:73` |
| `sec` | `record` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/config/KeyConfig/node.ndf:96` |
| `  filename` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/config/KeyConfig/node.ndf:113` |
| `  secret` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/config/KeyConfig/node.ndf:132` |


## Document References

No document dependencies were extracted.


## Referenced By Services

| Service | Usage | Resolved | Occurrences |
| --- | --- | --- | ---: |
| `pgp.services.common:readConfig` | `OUTPUT` | True | 1 |
| `pgp.services.common:selectFromConfig` | `OUTPUT` | True | 1 |


## Referenced By Processes

No process-document relationships were derived for this document.


## Referenced By Documents

| Document | Resolved | Occurrences |
| --- | --- | ---: |
| `pgp.documents.config:PGPconfig` | True | 1 |


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

- Document metadata: `PGP/ns/pgp/documents/config/KeyConfig/node.ndf`:4

## Analysis Limitations

M3 extracts technical Document Type structure and document-reference evidence. It does not validate mapping paths against schemas, infer business meaning, or expand referenced documents recursively.
