# ADR-0001: WmDocGen Explorer is a static React app over a versioned data projection

- Status: Accepted (M13 PoC, implemented on the `explorer` branch in four steps)
- Scope: `wm-doc explorer build|demo|serve`, `src/wm_doc/explorer/`, `explorer-ui/`

## Context

Engineers need to search an Integration Server of about 7,300 services and 9,600 document
types, read what a service does, see what it calls and what calls it, and move through the
call graph. The Markdown site cannot do that interactively. `analysis.json` (about 600 MB at
that size) is the complete, canonical record and is far too large for a browser.

Constraints: offline and fully static (no backend, database, authentication or connection to
Integration Server); analysed packages are never executed or modified; all package text and
descriptions are untrusted; existing outputs stay unchanged; demos must not use real data.

## Decision

1. **A projection, not a subset.** `wm_doc.explorer` turns the in-memory `AnalysisResult`
   and the existing facts (callers, entry points, data effects, package summaries,
   description states as `wm-doc status` computes them) into a small contract,
   `wm-doc-explorer.v1`: `manifest.json`, `search.json`, `graph.json`, `overview.json`, one
   file per service and one per package. The contract has its own lowercase vocabulary,
   is defined once in pydantic, exported as JSON Schema, and the TypeScript types are
   generated from that schema. Files are named by hashed IDs (Windows cannot tell names
   apart that differ only in case).
2. **Python owns every fact.** All resolution and classification happens in Python; the
   classification of call targets is shared with focused publication
   (`wm_doc/call_targets.py`). The app only displays facts and walks emitted edges within
   limits. A cross-language test proves the graph walk reaches exactly the services
   `analyze --target-service X --dependency-depth N` publishes.
3. **A React + TypeScript + Vite app, prebuilt and shipped in the Python package.** Users
   need no Node.js; the build is reproducible and committed. The app reads data through
   one repository interface, so a future REST backend can replace the static files.
4. **Text is never markup.** Text arrives as plain segments (`text`, or `code` with the ID
   of the service it names exactly); React renders them as text. Prose passes the
   disclosure scan or is withheld and counted. Designer comments, Notes, literal values
   (also inside data effects), SQL and connection properties are never exported. A strict
   Content Security Policy, no external requests, lint rules against HTML injection.
5. **A bounded graph with React Flow and dagre** (instead of Cytoscape): depth 1–4, node
   limit 50/150/300, at most 25 new neighbours per node with "+N more", built-ins hidden by
   default, a list view as the accessible alternative. Laid out along the walk's spanning
   tree; loaded only on service pages.
6. **Demos use synthetic packages only** (`wm-doc explorer demo`), which go through the real
   analysis and carry descriptions in every review state, including hostile and
   secret-like text to show it is handled.

## Consequences

- Opening a service fetches a few kilobytes; the whole server is never downloaded.
  Measured at 7,300 services and 9,600 document types: export after analysis about 12 s
  and 270 MB, 27 MB of data in total, `search.json` 1.1 MB, `graph.json` 0.7 MB; main
  JavaScript 110 KB compressed, graph code 77 KB loaded on demand. In the browser: 1.5 MB
  loaded at start, search usable in about 1.1 s, about 30 ms per keystroke, a service opens
  in about 150 ms, and the graph of a service with 7,300 callers stays at 28 nodes.
- A second toolchain for developers (Node.js 22+, npm with exact versions installed with
  `--ignore-scripts`) and a committed build artifact that must be rebuilt with every app
  change.
- An explorer built from real packages contains internal names (services, tables, queues,
  connections) and must not be shared; the app says so on every page.
- Description states are only as fresh as the description files; they match `wm-doc status`
  for the same inputs.

## Alternatives considered

- **MkDocs Material over the generated Markdown:** builds of 7,300+ pages are slow, a
  full-text index is tens of megabytes, Markdown passes raw HTML through (an XSS path), and
  the graph would be bolted on.
- **Jinja HTML pages with small vanilla-JavaScript islands:** no Node.js, but untyped,
  hand-tested interactivity, rendering logic duplicated in two places, and no path to a
  backend.
- **Cytoscape.js for the graph:** draws on a canvas that screen readers and browser tests
  cannot see; its strength (thousands of nodes) is exactly what the node limits rule out.
  React Flow's DOM nodes let the browser tests find two real bugs (unclickable links in
  nodes, misplaced edge handles).

## Notes from the implementation

- ESLint is pinned to 9 because `eslint-plugin-jsx-a11y` does not support ESLint 10 yet.
- Dependencies were installed with `npm install --before=<date three weeks earlier>` and
  exact versions; all bundled licences are permissive (MIT, ISC, BSD-3-Clause), listed in
  `THIRD-PARTY.txt` next to the app.
- No CI workflow was added; the checks run locally (`uv run pytest`, `npm run check`,
  `npm run e2e`, and the slow scale checks `uv run pytest -m slow` and `npm run e2e:scale`).
- Deferred: document type pages, a FLOW outline view, `processes.yml` process views, a
  package-level graph, full-text search over whole descriptions, editing or approving in the
  app, a REST backend, authentication, Firefox and WebKit browser tests.
