# Unsupported Constructs

Unsupported or only partially supported in M2a:

- Full FLOW execution semantics
- Full MAP operation semantics
- Detailed data lineage across `MAPCOPY`, `MAPSET`, `MAPDELETE`, `MAPSOURCE`, `MAPTARGET`, and `DATA`
- Full `BRANCH` condition evaluation
- Full `LOOP` iteration simulation
- `REPEAT` semantics
- Runtime effects of `EXIT`
- Dynamic service invocation resolution
- Document reference dependency extraction
- Java service body decoding or analysis
- JDBC Adapter Services
- Universal Messaging triggers
- JMS triggers
- Schedulers
- Process models
- Runtime-only Integration Server configuration
- Ollama documentation generation

M2a extracts static `INVOKE` and `MAPINVOKE` targets when a literal `SERVICE` attribute is present.
Targets that are not present in the analyzed snapshot are retained as unresolved call occurrences
and unresolved unique dependencies with source evidence.

M2a parses observed `EXIT` elements into typed FLOW nodes. Unknown EXIT shapes remain parsed but also
produce explicit findings.

M2a treats `MAP` as a structural container so nested `MAPINVOKE` calls can be positioned in the
ordered FLOW tree. `MAPCOPY`, `MAPSET`, `MAPDELETE`, `MAPSOURCE`, `MAPTARGET`, and `DATA` remain
deferred to M2b and produce `MAP_OPERATION_DEFERRED` findings.

Unsupported files currently include PGP Java source/classes, key files, public resources, Eclipse
metadata, and config files. Inventory records their paths and sizes only; it does not render file
contents.

Observed but not interpreted uppercase FLOW elements currently produce `UNSUPPORTED_FLOW_ELEMENT`
findings. In the current OAAdapter fixture, generic unsupported findings are no longer emitted for
structural `MAP` or the supported observed `EXIT` shape.
