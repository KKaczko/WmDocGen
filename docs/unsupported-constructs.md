# Unsupported Constructs

Unsupported or only partially supported in M1:

- Full FLOW execution semantics
- Full MAP operation semantics
- Detailed data lineage across `MAPCOPY`, `MAPSET`, `MAPDELETE`, `MAPSOURCE`, `MAPTARGET`, and `DATA`
- Full `BRANCH`, `LOOP`, `REPEAT`, and `EXIT` semantics
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

M1 extracts static `INVOKE` and `MAPINVOKE` targets when a literal `SERVICE` attribute is present.
Targets that are not present in the analyzed snapshot are retained as unresolved dependencies with
source evidence.

Unsupported files currently include PGP Java source/classes, key files, public resources, Eclipse
metadata, and config files. Inventory records their paths and sizes only; it does not render file
contents.

Observed but not interpreted FLOW elements currently produce `UNSUPPORTED_FLOW_ELEMENT` findings.
For OAAdapter this includes `MAP`, `MAPCOPY`, `MAPSET`, `MAPDELETE`, `MAPSOURCE`, `MAPTARGET`, `DATA`,
and `EXIT`.
