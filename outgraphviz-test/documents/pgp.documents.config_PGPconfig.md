# pgp.documents.config:PGPconfig

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.documents.config` |
| Document | `PGPconfig` |
| Basis | `CONFIRMED` |
| Declared package | `PGP` |

## Description

No description was declared in supported metadata.

## Field Hierarchy

| Field | Type | Dimension | Optional | Document Reference | Source |
| --- | --- | --- | --- | --- | --- |
| `@version` | `string` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/config/PGPconfig/node.ndf:18` |
| `keys` | `record` | `0` / `SCALAR` |  | `` | `PGP/ns/pgp/documents/config/PGPconfig/node.ndf:37` |
| `  keys` | `recref` | `1` / `LIST` |  | `pgp.documents.config:KeyConfig` | `PGP/ns/pgp/documents/config/PGPconfig/node.ndf:54` |


## Document References

| Document | Resolved | Occurrences |
| --- | --- | ---: |
| `pgp.documents.config:KeyConfig` | True | 1 |


## Referenced By Services

| Service | Usage | Resolved | Occurrences |
| --- | --- | --- | ---: |
| `pgp.services.common:selectFromConfig` | `INPUT` | True | 1 |


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

- Document metadata: `PGP/ns/pgp/documents/config/PGPconfig/node.ndf`:4

## Analysis Limitations

M3 extracts technical Document Type structure and document-reference evidence. It does not validate mapping paths against schemas, infer business meaning, or expand referenced documents recursively.
