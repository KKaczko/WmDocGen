# oa.adapter.geographicAddressManagement:createGeographicAddressValidation

## Identity

| Field | Value |
| --- | --- |
| Package | `OAAdapter` |
| Namespace | `oa.adapter.geographicAddressManagement` |
| Service | `createGeographicAddressValidation` |
| Type | `FLOW` |
| Importance | `NORMAL` |
| Layer | `UNKNOWN` |
| Identity basis | `RECONSTRUCTED` |

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


## Static Invoked Services

| Invoke | Resolved | Target |
| --- | --- | --- |
| `i0002` | False | `oa.adapter.services.common:getProviderConnection` |
| `i0005` | False | `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations` |
| `i0006` | False | `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations` |
| `i0007` | False | `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations` |
| `i0009` | False | `oa.adapter.services.geographicAddressManagement.geographicAddressValidation:getGeographicAddressValidation` |
| `i0010` | False | `oa.adapter.services.common:isPatchAllowed` |
| `i0013` | False | `oa.adapter.services.geographicAddressManagement.geographicAddress:createGeographicAddress` |
| `i0014` | False | `oa.adapter.services.geographicAddressManagement.geographicAddress:createGeographicAddress` |
| `i0018` | False | `oa.adapter.db_flow._create:createGeographicAddresssValidation` |
| `i0019` | False | `oa.adapter.db_flow._create:createGAVFailReason` |
| `i0024` | False | `oa.adapter.services.common:checkErrorResult` |
| `i0025` | False | `oa.adapter.services.geographicAddressManagement.geographicAddressValidation:getGeographicAddressValidation` |
| `i0026` | False | `oa.adapter.services.geographicAddressManagement.geographicAddressValidation:getGeographicAddressValidation` |
| `i0027` | False | `oa.adapter.services.geographicAddressManagement.geographicAddress:getGeographicAddress` |
| `i0030` | False | `oa.adapter.db_flow._get:getNewEventId` |
| `i0034` | False | `oa.adapter.services.common:saveEvent` |
| `i0040` | False | `oa.adapter.services.common:checkErrorResult` |
| `i0042` | False | `oa.adapter.services.common:checkErrorResult` |
| `i0001` | False | `pub.list:sizeOfList` |
| `i0003` | False | `pub.list:sizeOfList` |
| `i0004` | False | `pub.string:toUpper` |
| `i0008` | False | `pub.list:sizeOfList` |
| `i0011` | False | `di.utils.bool:strBoolToNumber` |
| `i0012` | False | `inea.utils:stringToDate` |
| `i0015` | False | `di.utils.bool:strBoolToNumber` |
| `i0016` | False | `di.utils:generateTransactionName` |
| `i0017` | False | `pub.art.transaction:startTransaction` |
| `i0020` | False | `pub.art.transaction:commitTransaction` |
| `i0021` | False | `pub.art.transaction:rollbackTransaction` |
| `i0022` | False | `pub.flow:getLastError` |
| `i0023` | False | `pub.art.transaction:rollbackTransaction` |
| `i0028` | False | `di.utils:nullToUnspecified` |
| `i0029` | False | `pub.date:formatDate` |
| `i0031` | False | `pub.date:getCurrentDateString` |
| `i0032` | False | `di.utils:generateTransactionName` |
| `i0033` | False | `pub.art.transaction:startTransaction` |
| `i0035` | False | `pub.art.transaction:commitTransaction` |
| `i0036` | False | `pub.publish:publish` |
| `i0037` | False | `pub.art.transaction:rollbackTransaction` |
| `i0038` | False | `pub.flow:getLastError` |
| `i0039` | False | `pub.art.transaction:rollbackTransaction` |
| `i0041` | False | `pub.flow:getLastError` |
| `i0043` | False | `pub.flow:clearPipeline` |

## Unsupported Or Unknown Constructs

- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`: FLOW element DATA is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`: FLOW element EXIT is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`: FLOW element MAP is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`: FLOW element MAPCOPY is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`: FLOW element MAPDELETE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`: FLOW element MAPSET is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`: FLOW element MAPSOURCE is observed but not interpreted in M1.
- PARTIALLY_SUPPORTED `UNSUPPORTED_FLOW_ELEMENT` at `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`: FLOW element MAPTARGET is observed but not interpreted in M1.

## Source Evidence

- Service metadata: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/node.ndf`
- Signature metadata: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/node.ndf`
- Invoke `i0001` target `pub.list:sizeOfList`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0002` target `oa.adapter.services.common:getProviderConnection`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0003` target `pub.list:sizeOfList`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0004` target `pub.string:toUpper`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0005` target `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0006` target `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0007` target `oa.adapter.services.geographicAddressManagement.geographicAddress:findGeographicAddressesForValidations`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0008` target `pub.list:sizeOfList`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0009` target `oa.adapter.services.geographicAddressManagement.geographicAddressValidation:getGeographicAddressValidation`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0010` target `oa.adapter.services.common:isPatchAllowed`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0011` target `di.utils.bool:strBoolToNumber`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0012` target `inea.utils:stringToDate`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0013` target `oa.adapter.services.geographicAddressManagement.geographicAddress:createGeographicAddress`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0014` target `oa.adapter.services.geographicAddressManagement.geographicAddress:createGeographicAddress`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0015` target `di.utils.bool:strBoolToNumber`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0016` target `di.utils:generateTransactionName`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0017` target `pub.art.transaction:startTransaction`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0018` target `oa.adapter.db_flow._create:createGeographicAddresssValidation`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0019` target `oa.adapter.db_flow._create:createGAVFailReason`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0020` target `pub.art.transaction:commitTransaction`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0021` target `pub.art.transaction:rollbackTransaction`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0022` target `pub.flow:getLastError`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0023` target `pub.art.transaction:rollbackTransaction`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0024` target `oa.adapter.services.common:checkErrorResult`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0025` target `oa.adapter.services.geographicAddressManagement.geographicAddressValidation:getGeographicAddressValidation`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0026` target `oa.adapter.services.geographicAddressManagement.geographicAddressValidation:getGeographicAddressValidation`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0027` target `oa.adapter.services.geographicAddressManagement.geographicAddress:getGeographicAddress`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0028` target `di.utils:nullToUnspecified`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0029` target `pub.date:formatDate`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0030` target `oa.adapter.db_flow._get:getNewEventId`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0031` target `pub.date:getCurrentDateString`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0032` target `di.utils:generateTransactionName`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0033` target `pub.art.transaction:startTransaction`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0034` target `oa.adapter.services.common:saveEvent`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0035` target `pub.art.transaction:commitTransaction`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0036` target `pub.publish:publish`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0037` target `pub.art.transaction:rollbackTransaction`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0038` target `pub.flow:getLastError`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0039` target `pub.art.transaction:rollbackTransaction`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0040` target `oa.adapter.services.common:checkErrorResult`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0041` target `pub.flow:getLastError`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0042` target `oa.adapter.services.common:checkErrorResult`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`
- Invoke `i0043` target `pub.flow:clearPipeline`: `OriginalSmall/OAAdapter/ns/oa/adapter/geographicAddressManagement/createGeographicAddressValidation/flow.xml`

## Analysis Limitations

M1 extracts declared signatures, structural container paths and static `INVOKE`/`MAPINVOKE`
targets. It does not interpret MAP transformations, branch semantics, EXIT behavior, retry
semantics, dynamic invocation targets, Java code, adapter metadata, triggers or process models.