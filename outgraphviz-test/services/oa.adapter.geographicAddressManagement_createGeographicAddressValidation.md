# oa.adapter.geographicAddressManagement:createGeographicAddressValidation

## Identity

| Field | Value |
| --- | --- |
| Package | `OAAdapter` |
| Namespace | `oa.adapter.geographicAddressManagement` |
| Service | `createGeographicAddressValidation` |
| Type | `FLOW` |
| Source service type | `flow` |
| Analysis support | `FULL` |
| Description status | `NO_DESCRIPTION` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

## Analysis Support

The artifact was analyzed by the supported parser for its service type.

## Description

No description was declared in supported metadata.

## Input Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `input` | `recref` | 0 |  | `oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput` |


## Output Signature

| Field | Type | Dim | Optional | Document Reference |
| --- | --- | ---: | --- | --- |
| `output` | `recref` | 0 |  | `oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput` |


## Document Type Usage

### Input Document Types

| Usage | Resolved | Document | Occurrences |
| --- | --- | --- | ---: |
| `INPUT` | False | `oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput` | 1 |


### Output Document Types

| Usage | Resolved | Document | Occurrences |
| --- | --- | --- | ---: |
| `OUTPUT` | False | `oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput` | 1 |


### Resolved Document References

No document reference occurrences were extracted for this section.


### Unresolved Document References

| Usage | Field | Resolved | Target | Source |
| --- | --- | --- | --- | --- |
| `INPUT` | `input` | False | `oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/node.ndf:19` |
| `OUTPUT` | `output` | False | `oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/node.ndf:53` |



## FLOW Overview

| Metric | Count |
| --- | ---: |
| Sequences | 32 |
| Branches | 27 |
| Loops | 2 |
| Exits | 9 |
| Call occurrences | 43 |
| Unique dependencies | 25 |

## Mapping Overview

| Metric | Count |
| --- | ---: |
| Flow maps | 135 |
| Copy operations | 190 |
| Set operations | 21 |
| Delete operations | 8 |
| Transformer bindings | 168 |
| Transformer input bindings | 112 |
| Transformer output bindings | 56 |
| Partially interpreted mappings | 21 |
| Literal policy | `redact` |
| Free-text policy | `include` |

## Mapping Copies

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_8d7f719007d7a5a2` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/id;1;0` | `/geographicAddressValidationIdOld;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:174` |
| `mapop_22ca1202b1b48009` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/alternateGeographicAddress;4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/fromList;3;1` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:458` |
| `mapop_d384fa48d0fec41c` | `/size;1;0` | `/alternateAddressListSize;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:466` |
| `mapop_d4b54b06d7bfadae` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope` | `/input;4;0;oa.adapter.doc.common:docGetProviderConnectionInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:653` |
| `mapop_d2c42fe128fc5441` | `/output;4;0;oa.adapter.doc.common:docGetProviderConnectionOutput/connectionName;1;0` | `/connectionName;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:661` |
| `mapop_5b1d3c9debae28cf` | `/output;4;0;oa.adapter.doc.common:docGetProviderConnectionOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:664` |
| `mapop_1793621ad4f30bf0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/geographicSubAddress;4;1;oa.model.geographicAddressManagement:docGeographicSubAddress` | `/fromList;3;1` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:882` |
| `mapop_ba867e1d3c211b1c` | `/size;1;0` | `/subAddressListSize;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:890` |
| `mapop_e9c940a9d4e286a8` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/geographicSubAddress;4;0;oa.model.geographicAddressManagement:docGeographicSubAddress/subUnitType;1;0` | `/inString;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1131` |
| `mapop_674ecdceabf82760` | `/value;1;0` | `/subUnitType;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1139` |
| `mapop_dc58c9618addfb5f` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/geographicSubAddress;4;0;oa.model.geographicAddressManagement:docGeographicSubAddress` | `/flatSubAddress;4;0;oa.model.geographicAddressManagement:docGeographicSubAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1396` |
| `mapop_102ad3ba7f3a4f18` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope/provider;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope/provider;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1678` |
| `mapop_df1142ba4b5b9aac` | `/flatSubAddress;4;0;oa.model.geographicAddressManagement:docGeographicSubAddress/subUnitNumber;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/subAddressUnitNumber;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1681` |
| `mapop_e14c94ebbd302c3d` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/streetNr;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/streetNr;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1684` |
| `mapop_2ec44816e04764c3` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/streetName;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/streetName;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1687` |
| `mapop_bd181c5f8cb6e1ef` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/city;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/city;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1690` |
| `mapop_c4d25e5dcaad7664` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1698` |
| `mapop_19601f3653d39e31` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressOutput/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1701` |
| `mapop_48d02bf54a865d92` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope/provider;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope/provider;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1991` |
| `mapop_4d4acfedf33bda8f` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/streetNr;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/streetNr;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1994` |
| `mapop_8277f021dc9a56c8` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/terc;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/terc;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1997` |
| `mapop_eb1238041dc899f0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/simc;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/simc;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2000` |
| `mapop_a5e7948664bf5bb6` | `/flatSubAddress;4;0;oa.model.geographicAddressManagement:docGeographicSubAddress/subUnitNumber;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/subAddressUnitNumber;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2003` |
| `mapop_6d2f5bbb531590d1` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/streetName;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/streetName;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2006` |
| `mapop_b596c8ba284f1ade` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2014` |
| `mapop_cb19ff2122b0bdd9` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressOutput/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2017` |
| `mapop_692b14d012e366f7` | `/geographicAddresses;4;0;oa.model.geographicAddressManagement:docGeographicAddress` | `/geographicAddressesTEMP;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2342` |
| `mapop_628ab84ce048ca90` | `/geographicAddressesTEMP;4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2824` |
| `mapop_d282353ff61a3604` | `/flatSubAddress;4;0;oa.model.geographicAddressManagement:docGeographicSubAddress/subUnitNumber;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/subAddressUnitNumber;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3104` |
| `mapop_7761e92d54f0c796` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/streetNr;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/streetNr;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3107` |
| `mapop_c7a814fd4fdd049f` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/terc;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/terc;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3110` |
| `mapop_ffdf0694f7bc1d72` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/simc;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/simc;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3113` |
| `mapop_ea97f15017c65c77` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/ulic;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/ulic;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3116` |
| `mapop_dff695eb9d34a0d1` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3119` |
| `mapop_360b481775789a7e` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressOutput/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3127` |
| `mapop_02f204a4f6902fca` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3130` |
| `mapop_5dd33b844abfdde2` | `/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/fromList;3;1` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3427` |
| `mapop_b38d5b96e4769cb0` | `/size;1;0` | `/geographicAddressListSize;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3435` |
| `mapop_6eafbfaa965f46d6` | `/geographicAddresses[0];4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/oldGeographicAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3752` |
| `mapop_36eeb431b8c18edd` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/id;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docGetGeographicAddressValidationInput/geographicAddressValidationId;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4138` |
| `mapop_9cf393a75e10af3f` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docGetGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4141` |
| `mapop_b1453b9d36b90689` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docGetGeographicAddressValidationOutput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation` | `/oldGeographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4149` |
| `mapop_7973e08ec62cd45e` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docGetGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4152` |
| `mapop_2d3afac111f6331d` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docGetGeographicAddressValidationOutput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/status;1;0` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/status;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4155` |
| `mapop_1301e9c6658874bd` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docGetGeographicAddressValidationOutput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validationResult;1;0` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/validationResult;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4158` |
| `mapop_536c8bc26ccc55f0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope/role;1;0` | `/input;4;0;oa.adapter.doc.common:docIsPatchAllowedInput/role;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4592` |
| `mapop_a8f9402ab0ef5229` | `/oldGeographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/status;1;0` | `/input;4;0;oa.adapter.doc.common:docIsPatchAllowedInput/status;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4595` |
| `mapop_1813e15df7e5e743` | `/output;4;0;oa.adapter.doc.common:docIsPatchAllowedOutput/isAllowed;3.1;0` | `/isPatchAllowed;3.1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4603` |
| `mapop_ab328f3237b2d000` | `/output;4;0;oa.adapter.doc.common:docIsPatchAllowedOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4606` |
| `mapop_571d5795cd6825f4` | `/oldGeographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/id;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/id;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:5356` |
| ... | ... | ... | 140 additional operations omitted | ... |


## Mapping Sets

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_ce0bd54ee1be34d9` |  | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult/errorCode;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:118` |
| `mapop_7547ca3e5ae2b411` |  | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult/errorDescription;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:146` |
| `mapop_5e21a18e9f11b90b` |  | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/status;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:268` |
| `mapop_1e7e1189d34f2907` |  | `/geographicAddressValidationListSize;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4110` |
| `mapop_fddb3bd402c7db26` |  | `/input;4;0;oa.adapter.doc.common:docIsPatchAllowedInput/disallowedStatus;1;1` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4551` |
| `mapop_35bed8cc4a4fe070` |  | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult/errorDescription;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4838` |
| `mapop_0e133e4918f9c318` |  | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult/errorDetails;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4867` |
| `mapop_7359aad6efeab696` |  | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult/errorCode;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4896` |
| `mapop_ef54a7b31624fca5` |  | `/pattern;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:5789` |
| `mapop_d63c70b2ec6ab87b` |  | `/envelope;4;0;cdm.common.baseType:docEnvelope/disableTransaction;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:9694` |
| `mapop_7ffc62cc45524513` |  | `/envelope;4;0;cdm.common.baseType:docEnvelope/disableTransaction;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:10850` |
| `mapop_e94647bcda6aac6e` |  | `/geographicAddressNotification;4;0;oa.hub.geographicAddressValidationManagement:docGeographicAddressValidationHub/eventType;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:17191` |
| `mapop_f7e1eebe6624db2b` |  | `/pattern;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:17954` |
| `mapop_6a9a7421abd3af78` |  | `/geographicAddressNotification;4;0;oa.hub.geographicAddressValidationManagement:docGeographicAddressValidationHub/eventType;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:18357` |
| `mapop_7fbc3827a366456c` |  | `/timezone;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:20211` |
| `mapop_27fbba4fdb83982f` |  | `/pattern;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:20232` |
| `mapop_d7864f6c6ae5d338` |  | `/input;4;0;oa.adapter.doc.common:docSaveEventInput/management;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:21816` |
| `mapop_ce8988522c24cdcf` |  | `/input;4;0;oa.adapter.doc.common:docSaveEventInput/resourceName;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:21844` |
| `mapop_98cbe9dc5846a56b` |  | `/documentTypeName;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:22805` |
| `mapop_852da00db5797d87` |  | `/delayUntilServiceSuccess;1;0` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:22825` |
| `mapop_eca510b905409adf` |  | `/preserve;1;1` | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:26532` |


## Mapping Deletes

| Operation | Source | Target | Literal | Evidence |
| --- | --- | --- | --- | --- |
| `mapop_9dec9e6b7db42073` | `/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2532` |
| `mapop_35ac0ea19b93d4ae` | `/geographicAddressesTEMP;4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/geographicAddressesTEMP;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2535` |
| `mapop_8e42ffb73ab69164` | `/geographicAddressesTEMP;4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/geographicAddressesTEMP;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2827` |
| `mapop_cfa2c4eb343d6515` | `/startTransactionOutput;2;0` | `/startTransactionOutput;2;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:9140` |
| `mapop_cfc6d9b093f22c82` | `/adapterErrorResult;4;0;cdm.common.baseType:docErrorResult` | `/adapterErrorResult;4;0;cdm.common.baseType:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:10276` |
| `mapop_9216e07878c0b7e3` | `/adapterErrorResult;4;0;cdm.common.baseType:docErrorResult` | `/adapterErrorResult;4;0;cdm.common.baseType:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:11457` |
| `mapop_d5b23a49493c2688` | `/adapterErrorResult;4;0;cdm.common.baseType:docErrorResult` | `/adapterErrorResult;4;0;cdm.common.baseType:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:12462` |
| `mapop_63f409b26d1118c2` | `/adapterErrorResult;4;0;cdm.common.baseType:docErrorResult` | `/adapterErrorResult;4;0;cdm.common.baseType:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:19829` |


## Transformer Bindings

| Binding | Direction | Transformer | Pipeline | Literal | Evidence |
| --- | --- | --- | --- | --- | --- |
| `bind_eeed274289618e22` | `INTO_TRANSFORMER` | `/fromList;3;1` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/alternateGeographicAddress;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:458` |
| `bind_d7ae3dc321fcfc85` | `FROM_TRANSFORMER` | `/size;1;0` | `/alternateAddressListSize;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:466` |
| `bind_b116391c69ec3165` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.common:docGetProviderConnectionInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:653` |
| `bind_9d62255ccc5d07fb` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.common:docGetProviderConnectionOutput/connectionName;1;0` | `/connectionName;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:661` |
| `bind_47677e07e3b510ed` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.common:docGetProviderConnectionOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:664` |
| `bind_c28c1df424e2a69b` | `INTO_TRANSFORMER` | `/fromList;3;1` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/geographicSubAddress;4;1;oa.model.geographicAddressManagement:docGeographicSubAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:882` |
| `bind_fc4edd1e9704c3bc` | `FROM_TRANSFORMER` | `/size;1;0` | `/subAddressListSize;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:890` |
| `bind_531b0810c3515900` | `INTO_TRANSFORMER` | `/inString;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/geographicSubAddress;4;0;oa.model.geographicAddressManagement:docGeographicSubAddress/subUnitType;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1131` |
| `bind_bfac2e7369fc6cb2` | `FROM_TRANSFORMER` | `/value;1;0` | `/subUnitType;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1139` |
| `bind_5924539c099781a9` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope/provider;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope/provider;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1678` |
| `bind_6ad70baf2f6472f5` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/subAddressUnitNumber;1;0` | `/flatSubAddress;4;0;oa.model.geographicAddressManagement:docGeographicSubAddress/subUnitNumber;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1681` |
| `bind_94bde2544a5feb98` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/streetNr;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/streetNr;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1684` |
| `bind_ad5b95b124c9203b` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/streetName;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/streetName;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1687` |
| `bind_c07e92c99bd7b914` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/city;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/city;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1690` |
| `bind_a94c992b926949e3` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1698` |
| `bind_eb721e18489bb391` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressOutput/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1701` |
| `bind_db50f414c75d4e7e` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope/provider;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope/provider;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1991` |
| `bind_782de2efe963df26` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/streetNr;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/streetNr;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1994` |
| `bind_2afd72b60d13719b` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/terc;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/terc;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1997` |
| `bind_6829e2dfb3e24fc9` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/simc;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/simc;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2000` |
| `bind_9849d6f8f55d638c` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/subAddressUnitNumber;1;0` | `/flatSubAddress;4;0;oa.model.geographicAddressManagement:docGeographicSubAddress/subUnitNumber;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2003` |
| `bind_f763740a8b887cb0` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/streetName;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/streetName;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2006` |
| `bind_2888782bd98df552` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2014` |
| `bind_c0684ea442b5502d` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressOutput/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:2017` |
| `bind_30cc9c26fefd2e6b` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/subAddressUnitNumber;1;0` | `/flatSubAddress;4;0;oa.model.geographicAddressManagement:docGeographicSubAddress/subUnitNumber;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3104` |
| `bind_84d6dc6de283ccc3` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/streetNr;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/streetNr;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3107` |
| `bind_4da9e15075648224` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/terc;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/terc;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3110` |
| `bind_39324c91a69dd302` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/simc;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/simc;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3113` |
| `bind_b59b6fc2e46bcb52` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/ulic;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validAddress;4;0;oa.model.geographicAddressManagement:docGeographicAddress/ulic;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3116` |
| `bind_0a007ec24d0f2504` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3119` |
| `bind_0d56dca7d41458e6` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressOutput/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` | `/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3127` |
| `bind_23c99d6f6b63db14` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddress:docFindGeographicAddressOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3130` |
| `bind_bca680004f778794` | `INTO_TRANSFORMER` | `/fromList;3;1` | `/geographicAddresses;4;1;oa.model.geographicAddressManagement:docGeographicAddress` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3427` |
| `bind_27928849b9475fdf` | `FROM_TRANSFORMER` | `/size;1;0` | `/geographicAddressListSize;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3435` |
| `bind_30a22acf11c4da0f` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docGetGeographicAddressValidationInput/geographicAddressValidationId;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/id;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4138` |
| `bind_48397f0255ceb09a` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docGetGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4141` |
| `bind_56175f2f056b1d37` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docGetGeographicAddressValidationOutput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation` | `/oldGeographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4149` |
| `bind_67f4c9eb66fe685e` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docGetGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4152` |
| `bind_9c94ab6dc4d43f46` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docGetGeographicAddressValidationOutput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/status;1;0` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/status;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4155` |
| `bind_4ba068fd74a77269` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docGetGeographicAddressValidationOutput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validationResult;1;0` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/validationResult;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4158` |
| `bind_9585216711070ade` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.common:docIsPatchAllowedInput/disallowedStatus;1;1` |  | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4551` |
| `bind_fa38eaa02317c780` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.common:docIsPatchAllowedInput/role;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/envelope;4;0;oa.model.SIDCommon.common.baseTypes:docEnvelope/role;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4592` |
| `bind_71f39d3ef4f23e02` | `INTO_TRANSFORMER` | `/input;4;0;oa.adapter.doc.common:docIsPatchAllowedInput/status;1;0` | `/oldGeographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/status;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4595` |
| `bind_f33bbe3a682be69e` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.common:docIsPatchAllowedOutput/isAllowed;3.1;0` | `/isPatchAllowed;3.1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4603` |
| `bind_245c6b9e7a38dab1` | `FROM_TRANSFORMER` | `/output;4;0;oa.adapter.doc.common:docIsPatchAllowedOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` | `/output;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationOutput/errorResult;4;0;oa.model.SIDCommon.common.baseTypes:docErrorResult` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4606` |
| `bind_bbd0e775560e6b05` | `INTO_TRANSFORMER` | `/booleanString;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/provideAlternative;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:5343` |
| `bind_c2b21233ebd60604` | `FROM_TRANSFORMER` | `/numberString;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/provideAlternative;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:5351` |
| `bind_d1bd6456d4a9286b` | `INTO_TRANSFORMER` | `/dateString;1;0` | `/input;4;0;oa.adapter.doc.geographicAddressManagement.geographicAddressValidation:docCreateGeographicAddressValidationInput/geographicAddressValidation;4;0;oa.model.geographicAddressManagement:docGeographicAddressValidation/validationDate;1;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:5786` |
| `bind_f171ca3c488654f5` | `INTO_TRANSFORMER` | `/pattern;1;0` |  | `<redacted:literal>` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:5789` |
| `bind_f9aea1b3dc4225ee` | `FROM_TRANSFORMER` | `/date;3.9;0` | `/validationDate;3.9;0` |  | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:5823` |
| ... | ... | ... | ... | 118 additional bindings omitted | ... |


## Normal Service Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 2 | False | `UNKNOWN` | `UNKNOWN` | `pub.art.transaction:commitTransaction` |
| 4 | False | `UNKNOWN` | `UNKNOWN` | `pub.art.transaction:rollbackTransaction` |
| 2 | False | `UNKNOWN` | `UNKNOWN` | `pub.art.transaction:startTransaction` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:clearPipeline` |
| 3 | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `pub.publish:publish` |


## Transformer Dependencies

| Occurrences | Resolved | Target Type | Target Support | Target |
| ---: | --- | --- | --- | --- |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.db_flow._create:createGAVFailReason` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.db_flow._create:createGeographicAddresssValidation` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.db_flow._get:getNewEventId` |
| 3 | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.common:checkErrorResult` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.common:getProviderConnection` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.common:isPatchAllowed` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.common:saveEvent` |
| 2 | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddress:createGeographicAddress` |
| 3 | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddress:getGeographicAddress` |
| 3 | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddressValidation:getGeographicAddressValidation` |
| 2 | False | `UNKNOWN` | `UNKNOWN` | `di.utils.bool:strBoolToNumber` |
| 2 | False | `UNKNOWN` | `UNKNOWN` | `di.utils:generateTransactionName` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `di.utils:nullToUnspecified` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `inea.utils:stringToDate` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `pub.date:formatDate` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `pub.date:getCurrentDateString` |
| 3 | False | `UNKNOWN` | `UNKNOWN` | `pub.list:sizeOfList` |
| 1 | False | `UNKNOWN` | `UNKNOWN` | `pub.string:toUpper` |


## Called By

No incoming static service calls target this service.


## Processes

This service is not part of any declared process.


## Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_7f90925dd59c17ec` | False | `UNKNOWN` | `UNKNOWN` | `pub.art.transaction:startTransaction` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:8537` |
| `call_c34943d257410500` | False | `UNKNOWN` | `UNKNOWN` | `pub.art.transaction:commitTransaction` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:11475` |
| `call_127efe89c161f253` | False | `UNKNOWN` | `UNKNOWN` | `pub.art.transaction:rollbackTransaction` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:11803` |
| `call_9a01b17dbf43a43d` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:12479` |
| `call_7d220e650f00daf0` | False | `UNKNOWN` | `UNKNOWN` | `pub.art.transaction:rollbackTransaction` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:12831` |
| `call_959e857f9ff3f45f` | False | `UNKNOWN` | `UNKNOWN` | `pub.art.transaction:startTransaction` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:20649` |
| `call_3eab69b2b17aa5ec` | False | `UNKNOWN` | `UNKNOWN` | `pub.art.transaction:commitTransaction` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:21902` |
| `call_8f4647e80bb3529d` | False | `UNKNOWN` | `UNKNOWN` | `pub.publish:publish` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:22338` |
| `call_b865957b0388b538` | False | `UNKNOWN` | `UNKNOWN` | `pub.art.transaction:rollbackTransaction` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:22858` |
| `call_f39b51892b895695` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:23341` |
| `call_3f4dc26a33299c92` | False | `UNKNOWN` | `UNKNOWN` | `pub.art.transaction:rollbackTransaction` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:23804` |
| `call_c05daae0711c7d59` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:getLastError` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:25146` |
| `call_57c7ed954fb69278` | False | `UNKNOWN` | `UNKNOWN` | `pub.flow:clearPipeline` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:26473` |


## Transformer Call Occurrences

| Call | Resolved | Target Type | Target Support | Target | Source |
| --- | --- | --- | --- | --- | --- |
| `call_429d78239a2dc8b1` | False | `UNKNOWN` | `UNKNOWN` | `pub.list:sizeOfList` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:450` |
| `call_38a8c7adac59f5c8` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.common:getProviderConnection` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:645` |
| `call_1d6173360ac5e894` | False | `UNKNOWN` | `UNKNOWN` | `pub.list:sizeOfList` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:874` |
| `call_b6c4a2c7194cb85f` | False | `UNKNOWN` | `UNKNOWN` | `pub.string:toUpper` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1123` |
| `call_20648c31d3bcd9a3` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1670` |
| `call_c9d0747fbd7ad64a` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:1983` |
| `call_1ad8ca6a55b07617` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3096` |
| `call_30246c833e833035` | False | `UNKNOWN` | `UNKNOWN` | `pub.list:sizeOfList` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:3419` |
| `call_ca10aba77bb15457` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddressValidation:getGeographicAddressValidation` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4130` |
| `call_8d8f0fe4c72d0903` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.common:isPatchAllowed` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:4543` |
| `call_db84c23e0b0e0da3` | False | `UNKNOWN` | `UNKNOWN` | `di.utils.bool:strBoolToNumber` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:5335` |
| `call_9ac40da0675a77c7` | False | `UNKNOWN` | `UNKNOWN` | `inea.utils:stringToDate` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:5778` |
| `call_2a59470aee4730c3` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddress:createGeographicAddress` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:6712` |
| `call_445c06894f847138` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddress:createGeographicAddress` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:7693` |
| `call_0bd630d97a69c8bc` | False | `UNKNOWN` | `UNKNOWN` | `di.utils.bool:strBoolToNumber` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:8238` |
| `call_caac6e8ffe21828b` | False | `UNKNOWN` | `UNKNOWN` | `di.utils:generateTransactionName` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:8510` |
| `call_474f0b71f898cd55` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.db_flow._create:createGeographicAddresssValidation` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:9656` |
| `call_02bba9f47a51fbc4` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.db_flow._create:createGAVFailReason` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:10833` |
| `call_376ee2a2623cc746` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.common:checkErrorResult` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:13808` |
| `call_21bfaca5a3463f97` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddressValidation:getGeographicAddressValidation` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:14453` |
| `call_facbbeec12f81cb8` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddressValidation:getGeographicAddressValidation` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:15111` |
| `call_882edcf0920061e4` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.geographicAddressManagement.geographicAddress:getGeographicAddress` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:15794` |
| `call_1b0a8fe0c9392e16` | False | `UNKNOWN` | `UNKNOWN` | `di.utils:nullToUnspecified` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:17219` |
| `call_2a81e57acbbcc0b0` | False | `UNKNOWN` | `UNKNOWN` | `pub.date:formatDate` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:17943` |
| `call_0ad4c1a4ff7e24c5` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.db_flow._get:getNewEventId` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:19087` |
| `call_3226f026b777bedd` | False | `UNKNOWN` | `UNKNOWN` | `pub.date:getCurrentDateString` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:20203` |
| `call_1894863885fd4234` | False | `UNKNOWN` | `UNKNOWN` | `di.utils:generateTransactionName` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:20627` |
| `call_cabc14e43e25d037` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.common:saveEvent` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:21793` |
| `call_3f9e56ada168fbf5` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.common:checkErrorResult` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:25114` |
| `call_617928d64334c064` | False | `UNKNOWN` | `UNKNOWN` | `oa.adapter.services.common:checkErrorResult` | `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml:26444` |


## FLOW Outline

- `fn0001` FLOW
-   `fn0002` SEQUENCE
-     `fn0003` MAP
-     `fn0004` BRANCH
-       `fn0005` BRANCH_CASE (%input/geographicAddressValidation/status% == $null)
-         `fn0006` MAP (%input/geographicAddressValidation/status% == $null )
-     `fn0007` MAP
-       `fn0008` MAPINVOKE (target=pub.list:sizeOfList)
-         `fn0009` MAP
-         `fn0010` MAP
-   `fn0011` SEQUENCE
-     `fn0012` SEQUENCE (try1)
-       `fn0013` MAP
-         `fn0014` MAPINVOKE (target=oa.adapter.services.common:getProviderConnection)
-           `fn0015` MAP
-           `fn0016` MAP
-       `fn0017` BRANCH
-         `fn0018` BRANCH_CASE (%connectionName% != $null)
-           `fn0019` SEQUENCE (%connectionName% != $null)
-             ... depth limit reached
-     `fn0284` SEQUENCE
-       `fn0285` INVOKE (target=pub.flow:getLastError)
-         `fn0286` MAP
-         `fn0287` MAP
-       `fn0288` MAP
-         `fn0289` MAPINVOKE (target=oa.adapter.services.common:checkErrorResult)
-           `fn0290` MAP
-           `fn0291` MAP
-   `fn0292` SEQUENCE
-     `fn0293` INVOKE (target=pub.flow:clearPipeline)
-       `fn0294` MAP


## Unsupported Or Unknown Constructs

No service-level findings.

## Source Evidence

- Service metadata: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/node.ndf`
- Signature metadata: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/node.ndf`
- MAPINVOKE `call_429d78239a2dc8b1` target `pub.list:sizeOfList`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:450- MAPINVOKE `call_38a8c7adac59f5c8` target `oa.adapter.services.common:getProviderConnection`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:645- MAPINVOKE `call_1d6173360ac5e894` target `pub.list:sizeOfList`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:874- MAPINVOKE `call_b6c4a2c7194cb85f` target `pub.string:toUpper`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:1123- MAPINVOKE `call_20648c31d3bcd9a3` target `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:1670- MAPINVOKE `call_c9d0747fbd7ad64a` target `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:1983- MAPINVOKE `call_1ad8ca6a55b07617` target `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:3096- MAPINVOKE `call_30246c833e833035` target `pub.list:sizeOfList`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:3419- MAPINVOKE `call_ca10aba77bb15457` target `oa.adapter.services.geographicAddressManagement.geographicAddressValidation:getGeographicAddressValidation`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:4130- MAPINVOKE `call_8d8f0fe4c72d0903` target `oa.adapter.services.common:isPatchAllowed`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:4543- MAPINVOKE `call_db84c23e0b0e0da3` target `di.utils.bool:strBoolToNumber`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:5335- MAPINVOKE `call_9ac40da0675a77c7` target `inea.utils:stringToDate`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:5778- MAPINVOKE `call_2a59470aee4730c3` target `oa.adapter.services.geographicAddressManagement.geographicAddress:createGeographicAddress`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:6712- MAPINVOKE `call_445c06894f847138` target `oa.adapter.services.geographicAddressManagement.geographicAddress:createGeographicAddress`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:7693- MAPINVOKE `call_0bd630d97a69c8bc` target `di.utils.bool:strBoolToNumber`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:8238- MAPINVOKE `call_caac6e8ffe21828b` target `di.utils:generateTransactionName`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:8510- INVOKE `call_7f90925dd59c17ec` target `pub.art.transaction:startTransaction`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:8537- MAPINVOKE `call_474f0b71f898cd55` target `oa.adapter.db_flow._create:createGeographicAddresssValidation`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:9656- MAPINVOKE `call_02bba9f47a51fbc4` target `oa.adapter.db_flow._create:createGAVFailReason`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:10833- INVOKE `call_c34943d257410500` target `pub.art.transaction:commitTransaction`:
  `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`:11475- Source evidence list truncated after 20 call occurrences in Markdown.
  Full evidence is in `analysis.json`.

## Analysis Limitations

M6 extracts observed FLOW, mapping, document-reference, Java Service source evidence, opaque service
common metadata, and user-declared process catalog evidence with literal and free-text disclosure
policies. It does not resolve mapped paths against document schemas, evaluate branch conditions,
simulate loops or runtime state, infer dynamic Java invocation targets, promote nested Java
executable bodies without a callback/control-flow model, execute Java code, compile Java source,
connect to Integration Server, or parse JDBC, trigger, scheduler, messaging, BPM process-model, or
database-resource semantics.