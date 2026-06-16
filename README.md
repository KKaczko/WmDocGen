# wm-doc

`wm-doc` is an offline, deterministic static-analysis tool for Software AG / IBM webMethods
Integration Server package snapshots.

The current implemented milestone is **M2b remediation for FLOW mapping extraction and disclosure
policies**. It discovers package and namespace artifacts, parses observed FLOW Service signatures,
extracts an ordered FLOW tree for observed structural nodes, separates static `INVOKE` call
occurrences from static `MAPINVOKE` transformer call occurrences, aggregates unique dependencies,
extracts observed `MAPCOPY`, `MAPSET`, `MAPDELETE`, map source/target metadata, and MAPINVOKE
transformer bindings, classifies services with configurable glob rules, resolves exact static
targets against discovered FLOW and Java Service metadata, and renders deterministic JSON, Markdown,
and Graphviz DOT outputs.

This is not a claim of full webMethods 10.15 compatibility. `samples/OriginalSmall/OAAdapter` is the
primary 10.15 fixture; `samples/PGP` is a compatibility and discovery corpus with unknown upstream
provenance.

## Quick Start

```powershell
wm-doc scan samples --output out\inventory
wm-doc analyze samples --output out\m2b-analysis
```

The scan command writes:

- `inventory.json`
- `fixture-inventory.md`

The analyze command writes:

- `analysis.json`
- `services/*.md`
- `graphs/dependencies.dot`

`analysis.json` uses schema `analysis.v4`. In this schema, call occurrences preserve each concrete
`INVOKE` or `MAPINVOKE` site, unique dependencies aggregate repeated calls by
`(caller, target, dependency kind)`, and mapping evidence is exposed as `flow_maps`,
`mapping_operations`, and `transformer_bindings`. Default DOT output remains a dependency graph:
one edge per unique dependency with occurrence counts, not pipeline mappings.

Literal extraction defaults to `redact`, while free-text metadata defaults to `include`. The secret
guard still redacts secret-like literal and free-text contexts even when inclusion is explicitly
enabled. Free-text policy is applied before canonical serialization, and raw attribute collections
are filtered so they cannot bypass the configured policy.

The tool works offline, treats analyzed packages as read-only, never connects to Integration Server,
and never executes analyzed Java or FLOW code.

## Development

The project is configured for Python 3.12+, `uv`, `pytest`, `ruff`, and `mypy`.

```powershell
uv run pytest
uv run ruff check .
uv run mypy
```

If `uv` is not installed, install it first or run the equivalent tools in a Python environment with
the dependencies from `pyproject.toml`.
