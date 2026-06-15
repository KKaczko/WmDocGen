# pgp.test.decrypt:testDecryptString

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.decrypt` |
| Service | `testDecryptString` |
| Type | `FLOW` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

## Description

Extracted description:

Bob receives a message from Alice
The message was encrypted with Bob's public key (available to everyone)
    and must be decrypted with Bob's private key (so only Bob can read it)

See http://en.wikipedia.org/wiki/Public-key_cryptography for more information on PGP

31-Mar-2011 :: Christian Schuit, Software AG :: Created

## Input Signature

No fields declared in supported metadata.


## Output Signature

No fields declared in supported metadata.


## Static Invoked Services

| Invoke | Resolved | Target |
| --- | --- | --- |
| `i0001` | True | `pgp.services.decrypt:decryptString` |
| `i0002` | False | `pub.flow:getLastError` |

## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/decrypt/testDecryptString/flow.xml`: FLOW element DATA is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/decrypt/testDecryptString/flow.xml`: FLOW element MAP is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/decrypt/testDecryptString/flow.xml`: FLOW element MAPCOPY is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/decrypt/testDecryptString/flow.xml`: FLOW element MAPSET is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/decrypt/testDecryptString/flow.xml`: FLOW element MAPSOURCE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/decrypt/testDecryptString/flow.xml`: FLOW element MAPTARGET is observed but not interpreted in M1.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/decrypt/testDecryptString/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/decrypt/testDecryptString/node.ndf`
- Invoke `i0001` target `pgp.services.decrypt:decryptString`: `PGP/ns/pgp/test/decrypt/testDecryptString/flow.xml`
- Invoke `i0002` target `pub.flow:getLastError`: `PGP/ns/pgp/test/decrypt/testDecryptString/flow.xml`

## Analysis Limitations

M1 extracts declared signatures, structural container paths and static `INVOKE`/`MAPINVOKE`
targets. It does not interpret MAP transformations, branch semantics, EXIT behavior, retry
semantics, dynamic invocation targets, Java code, adapter metadata, triggers or process models.