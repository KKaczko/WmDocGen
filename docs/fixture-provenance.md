# Fixture Provenance

## OriginalSmall / OAAdapter

`samples/OriginalSmall/OAAdapter` is a sanitized private fixture. The prompt identifies it as
originating from Software AG / IBM webMethods Integration Server 10.15.

Known provenance:

- Only the files included in this repository snapshot are available.
- The fixture has been represented to this project as sanitized.
- It is not a complete-package coverage claim.
- It is the primary source of truth for observed webMethods IS 10.15 behavior in this project.

Unknown or not claimed:

- Original repository, author, commit, and license are not available.
- Runtime Integration Server configuration is not available.
- No claim is made that this fixture represents all 10.15 package formats.

M5-lite fixture note:

- The current fixture set does not contain a real JDBC Adapter Service, trigger, scheduler, UM/JMS,
  process, or other opaque service artifact with an unsupported `svc_type`.
- Opaque service support is limited to common `node.ndf` metadata and exact dependency resolution.
  Synthetic tests validate that generic behavior, but they do not prove any adapter-specific
  serialization format.

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

The scanner reports this as `PGP_PROVENANCE_UNKNOWN`. PGP remains a compatibility corpus only; it is
not proof of full webMethods 10.15 compatibility.

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
