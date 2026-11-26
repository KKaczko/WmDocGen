# Fixture Provenance

## Synthetic / SampleOrders

`samples/Synthetic/SampleOrders` is a hand-written synthetic fixture. Every package, namespace,
service, document, field and literal name in it is invented.

- It contains one FLOW service, `sample.orders.intake:validateOrderBatch` (`node.ndf` and
  `flow.xml`), written in the IS 10.15 file format.
- It uses the FLOW constructs observed in real 10.15 services: TRY/CATCH sequences, SWITCH and
  label-expression branches with `$default` cases, a `LOOP` over an array, `EXIT` from labelled
  steps, `INVOKE` input/output maps with `MAPSOURCE`/`MAPTARGET` schemas, transformers
  (`MAPINVOKE`), `MAPSET` literals, a `MAPCOPY` with an indexed source, `MAPDELETE`, step
  comments, transactions, a publish with a literal document type, and calls to services that are
  not in the analysed packages.
- Its signature refers to two document types that are deliberately not in the fixture, so they
  stay unresolved.
- It replaced an earlier primary fixture that could not be redistributed. It is not a
  complete-package coverage claim.

M5-lite fixture note:

- Until M15 the fixture set did not contain a real JDBC Adapter Service; it still has no real
  trigger, scheduler, UM/JMS, native process-model, or other opaque service artifact with an
  unsupported `svc_type`.
- Opaque service support is limited to common `node.ndf` metadata and exact dependency resolution.
  Synthetic tests validate that generic behavior, but they do not prove any adapter-specific
  serialization format.

M6 fixture note:

- The checked-in `samples/` tree does not contain a default `processes.yml`.
- Process catalog tests use temporary user-authored YAML files outside the analyzed sample packages.
  They validate catalog parsing, exact entrypoint validation, traversal, process documentation, and
  per-process DOT output without modifying or adding evidence to the fixture packages.
- M6 does not prove native webMethods BPM/process-model serialization because no such fixture is
  present.

M7 fixture note:

- Graph publishing is derived from generated DOT files and does not add or modify fixture evidence.
- The default fixture analysis has two DOT graphs: service dependencies and document references.
  Test process catalogs outside `samples/` add per-process DOT graphs for renderer coverage.
- Local Graphviz availability is optional; normal tests use a deterministic fake renderer that emits
  valid SVG/PNG structures, and a real Graphviz audit is skipped when `dot` is not installed or not
  supplied through the test environment.
- Generated-output cleanup tests create temporary stale files, directories, and symlinks outside the
  fixture tree to prove managed output replacement without modifying `samples/`.

M8a fixture note:

- Focused publication scope tests run the complete fixture analysis first and then limit generated
  publication output. They do not modify `samples/`, add process evidence to fixture packages, or
  claim lower parsing cost.
- Service, namespace, package, and process scopes are validated with existing fixture services plus
  temporary process catalogs outside `samples/`.
- Focused output keeps full `analysis.json` as the canonical fixture snapshot and writes
  `scope.json` as derived publication metadata. Scoped DOT files use focused names such as
  `graphs/scope.dot` so they are not mistaken for global dependency or document graphs.

M12 fixture note:

- Description-file tests run `describe` over the samples, copies of them and synthetic packages
  with deterministic fake model responses. They do not modify `samples/`, install or require
  Ollama, or add business facts to fixture packages.
- Real Ollama use remains an optional local check. Model-written text is checked against the facts
  sent with each prompt and kept in separate description files, never in `analysis.json`.
- No production artifacts are in the repository. Trigger, descriptor, adapter-service and
  connection behaviour is covered by synthetic `node.ndf` files only.

## PGP

`samples/PGP` is a public compatibility and discovery corpus used as-is from the local repository
snapshot.

Observed metadata:

- Package directory name: `PGP`.
- Eclipse project name in `.project`: `WxPGP`.
- `manifest.v3` version: `1.0`.
- `manifest.v3` startup service references `wx.pgp.services.common:readConfig`.
- Package alias evidence observed by the scanner includes `GCS_PGP` and `WxPGP`.
- Java/config source headers include Software AG 2018 copyright text and `SPDX-License-Identifier:
  Apache-2.0`.
- Several files include Apache License 2.0 header text and a URL to the Apache license.

Unavailable in the local fixture:

- Upstream source URL: unknown.
- Exact upstream commit SHA: unknown.
- Standalone README: not present.
- Standalone LICENSE file: not present.
- Documented webMethods product version: unknown.

This is recorded here only; the scanner no longer emits a fixture-specific finding for a package
named `PGP`, because production code must not special-case test fixtures. PGP remains a
compatibility corpus only; it is not proof of full webMethods 10.15 compatibility.

## jdbcadapter

`samples/jdbcadapter/` holds two JDBC adapter services the repository owner created on a real
webMethods Integration Server 10.15 and exported (M15): `dynamicSQL/` and `customSQL/`, each
with its original `node.ndf` and the document IS decoded from its `IRTNODE_PROPERTY`
(`pub.string:base64Decode` -> `pub.document:bytesToDocument` ->
`pub.json:documentToJSONString`), plus the namespace folder's `node.idf`. The JSON files are the
reference for the decoder's golden tests (`tests/unit/test_idata_binary.py`); they are never
read during normal runs. The files are read-only and listed in `checksums.sha256`.

Content review: the SQL reads a test table (`TEST`, columns `id`, `name`, `quantity`, `desc`)
with test field names (`test1`, `test2`, `output_Test`, `out_test`); no credential values are
present (the `userid` and `password` settings hold the pipeline paths
`overrideCredentials.$dbUser` / `$dbPassword`, not secrets). Names that may be
organization- or person-specific: the connection `inea.configuration.jdbc:UtilsConnection`, the
namespace `kkaczk.jdbcadapter` and the designer locale `pl_PL`. Confirm or replace them before
publishing the repository (the tests read the folder names, not these values).

`samples/jdbcadapter/jdbcadapter2/` (added 2026-11-26, same export method) holds the namespace
folder's `node.idf` (`kkaczk.jdbcadapter.jdbcadapter2`) and `customSQLLong/`, a CustomSQL
service whose SQL template is 13,739 characters long: a 56-character `SELECT ... FROM DUAL`
with two bind parameters, followed by a placeholder-text block comment with Polish letters. It
is the evidence for the long string tag `0x84` (`docs/idata-binary-format.md`). Content
review: test field names (`test1`, `test2`, `testout`, `testoutSTR`), the same connection,
locale and credential pipeline paths as above; no credential values.

`samples/jdbcadapter/jdbcadapter3/` (added 2026-11-26, same export method) holds the namespace
folder's `node.idf` (`kkaczk.jdbcadapter.jdbcadapter3`) and `customSQL127/`, `customSQL128/`,
`customSQL255/`, `customSQL256/`: CustomSQL services whose SQL is a one-line
`SELECT 1 AS X FROM DUAL` with a digit-filled block comment, exactly 127, 128, 255 and 256
ASCII characters long. They are the evidence for the string length switch (one unsigned byte
up to 255, `0x84` from 256). No credential values.

## Sensitive Fixture Categories

Potentially sensitive fixture categories are present and should be reviewed before publishing this
repository:

- PGP demo public key files under `samples/PGP/pub/keys`.
- PGP demo secret key files under `samples/PGP/pub/keys`.
- PGP config metadata that references key filenames under `samples/PGP/config`.
- PGP Java source that contains key/password-handling code paths.

These files originate from the PGP sample corpus and are useful for parser discovery and fixture
integrity tests. They may be retained for an internal M1 baseline with this provenance note, but they
should be replaced with clearly safe synthetic fixtures or excluded before public publication unless
their redistribution status is confirmed.
