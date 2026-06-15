# pgp.test.encrypt:testEncryptFile

## Identity

| Field | Value |
| --- | --- |
| Package | `PGP` |
| Namespace | `pgp.test.encrypt` |
| Service | `testEncryptFile` |
| Type | `FLOW` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

## Description

Extracted description:

Alice sends a message to Bob
The message is encrypted with Bob's public key (available to everyone)
The message is signed with Alice's private key (available to Alice only)

See http://en.wikipedia.org/wiki/Public-key_cryptography for more information on PGP

31-Mar-2011 :: Christian Schuit, Software AG :: Created

## Input Signature

No fields declared in supported metadata.


## Output Signature

No fields declared in supported metadata.


## Static Invoked Services

| Invoke | Resolved | Target |
| --- | --- | --- |
| `i0001` | True | `pgp.services.common:getPackagePath` |
| `i0002` | True | `pgp.services.common:getPackagePath` |
| `i0003` | True | `pgp.services.encrypt:encryptFile` |
| `i0004` | False | `pub.flow:getLastError` |

## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`: FLOW element DATA is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`: FLOW element MAP is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`: FLOW element MAPCOPY is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`: FLOW element MAPSET is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`: FLOW element MAPSOURCE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`: FLOW element MAPTARGET is observed but not interpreted in M1.

## Source Evidence

- Service metadata: `PGP/ns/pgp/test/encrypt/testEncryptFile/node.ndf`
- Signature metadata: `PGP/ns/pgp/test/encrypt/testEncryptFile/node.ndf`
- Invoke `i0001` target `pgp.services.common:getPackagePath`: `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`
- Invoke `i0002` target `pgp.services.common:getPackagePath`: `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`
- Invoke `i0003` target `pgp.services.encrypt:encryptFile`: `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`
- Invoke `i0004` target `pub.flow:getLastError`: `PGP/ns/pgp/test/encrypt/testEncryptFile/flow.xml`

## Analysis Limitations

M1 extracts declared signatures, structural container paths and static `INVOKE`/`MAPINVOKE`
targets. It does not interpret MAP transformations, branch semantics, EXIT behavior, retry
semantics, dynamic invocation targets, Java code, adapter metadata, triggers or process models.