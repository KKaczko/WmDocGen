# pgp.test.decrypt:testDecryptAndVerifyUnsignedString

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.decrypt` |
| Service | `testDecryptAndVerifyUnsignedString` |
| Type | `FLOW` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

## Description

Extracted description:

Bob receives a UNSIGNED message from Alice
The message was encrypted with Bob's public key (available to everyone)
    and must be decrypted with Bob's private key (so only Bob can read it)
The message was signed with Alice's private key (available to Alice only)
    and must be verified with Alice's public key (so only Alice could have sent it)

UNSIGNED message is decrypted and verified == 0! No error!

See http://en.wikipedia.org/wiki/Public-key_cryptography for more information on PGP

31-Mar-2011 :: Christian Schuit, Software AG :: Created

## Input Signature

No fields declared in supported metadata.


## Output Signature

No fields declared in supported metadata.


## Static Invoked Services

| Invoke | Resolved | Target |
| --- | --- | --- |
| `i0001` | True | `pgp.services.decrypt:decryptAndVerifyString` |
| `i0002` | False | `pub.flow:getLastError` |

## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml`: FLOW element DATA is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml`: FLOW element MAP is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml`: FLOW element MAPCOPY is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml`: FLOW element MAPSET is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml`: FLOW element MAPSOURCE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml`: FLOW element MAPTARGET is observed but not interpreted in M1.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/node.ndf`
- Invoke `i0001` target `pgp.services.decrypt:decryptAndVerifyString`: `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml`
- Invoke `i0002` target `pub.flow:getLastError`: `PGP/ns/pgp/test/decrypt/testDecryptAndVerifyUnsignedString/flow.xml`

## Analysis Limitations

M1 extracts declared signatures, structural container paths and static `INVOKE`/`MAPINVOKE`
targets. It does not interpret MAP transformations, branch semantics, EXIT behavior, retry
semantics, dynamic invocation targets, Java code, adapter metadata, triggers or process models.