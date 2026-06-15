# Fixture Provenance

## OriginalSmall / OAAdapter

The prompt states that this is a real sanitized webMethods Integration Server 10.15 FLOW Service.
It is the primary source of truth for future 10.15 behavior.

## PGP

The public PGP package is used as-is from the local repository snapshot. The fixture contains Apache
2.0 headers in several files, but the repository does not include:

- upstream source URL
- exact commit SHA
- standalone license file
- README
- documented webMethods version

The scanner reports this as `PGP_PROVENANCE_UNKNOWN`.

M1 uses PGP to check that the FLOW parser is not hardcoded to the OAAdapter path. PGP remains a
compatibility corpus only; it is not proof of full webMethods 10.15 compatibility.
