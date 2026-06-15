# wm-doc

`wm-doc` is an offline, deterministic static-analysis tool for Software AG / IBM webMethods
Integration Server package snapshots.

The current implemented milestone is **M1 FLOW Service proof of concept**. It discovers package and
namespace artifacts, parses observed FLOW Service signatures, extracts observed FLOW containers and
static `INVOKE`/`MAPINVOKE` calls, classifies services with configurable glob rules, resolves static
dependencies against discovered FLOW and Java Service metadata, and renders deterministic JSON,
Markdown, and Graphviz DOT outputs.

This is not a claim of full webMethods 10.15 compatibility. `samples/OriginalSmall/OAAdapter` is the
primary 10.15 fixture; `samples/PGP` is a compatibility and discovery corpus with unknown upstream
provenance.

## Quick Start

```powershell
wm-doc scan samples --output out\inventory
wm-doc analyze samples --output out\m1-analysis
```

The scan command writes:

- `inventory.json`
- `fixture-inventory.md`

The analyze command writes:

- `analysis.json`
- `services/*.md`
- `graphs/dependencies.dot`

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
