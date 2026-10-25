# WmDocGen Explorer (M13 PoC)

The explorer is a static web app over the analysis: search every service and package, open a
service to see what it does (its reviewed description), its signature, calls, callers, entry
points, the data and systems it touches and its adapter configuration, and follow calls from
service to service. Every section says where its content comes from: static analysis, the
adapter configuration, or an AI description and its review state. Python builds the data;
the prebuilt app ships inside the Python package, so users need no Node.js. There is no
backend, database or connection to Integration Server.

Each service page also has a **call graph**: the service with its callers on the left and
callees on the right.

- Depth 1 to 4 means what `analyze --dependency-depth` means. You can show callers, callees or
  both, and switch built-in services on or off.
- The graph never shows the whole server. A node limit (50, 150 or 300) applies, and at most
  25 new neighbours are shown per service; the rest become one "+N more" node (also a button
  under the graph), which opens the full list. The `+` button on a service opens its next
  level; `−` closes it.
- "Show as list" gives the same neighbourhood as nested lists of links, for keyboard and
  screen-reader use.
- The settings live in the URL (`depth`, `dir`, `builtins`, `limit`, `view`), so Back restores
  them and a link can be shared.

The home page shows the server overview (when an approved one exists), counts, how much
was analysed and described, every package, and the packages left out of the analysis.
A package page shows its overview, its services (filter by name or type), its entry points
(services that work reaches from outside the package, and from where), the packages it
calls into and is called from, and the data and systems its own services touch.

## Using it

```bash
# Safe demo on generated (synthetic) packages and descriptions in every review state:
# nothing from your server is used.
wm-doc explorer demo -o out/explorer-demo
wm-doc explorer serve out/explorer-demo          # then open http://127.0.0.1:8765/

# Your own packages (internal: the app shows "do not share").
wm-doc explorer build C:/GIt/ESB -o out/explorer --docs-dir service-docs
wm-doc explorer serve out/explorer
```

- `build` takes the same package-selection, `--config`, `--processes-file`,
  `--external-systems` and `--platform-services` options as `analyze`, and reuses the analysis
  cache.
- `--descriptions approved` (default) shows reviewed descriptions, warning when the facts
  changed since approval; `all` also shows unreviewed drafts; `none` shows none. Designer
  comments and Notes are never shown.
- The output folder must be outside the packages folder; analysed packages are never written.
- Browsers do not load the app from `file://`, so serve the folder: `wm-doc explorer serve`
  (loopback only by default) or any static web server.

## Data contract `wm-doc-explorer.v1`

The app reads only these files, never `analysis.json`:

| File | Content |
| --- | --- |
| `data/manifest.json` | contract version, generator, dataset kind and label, disclosure settings, counts, content digest |
| `data/search.json` | every service (ID, name, package, kind, analysis level, description state, purpose line) and package |
| `data/graph.json` | every call as `[from, to, relation, count]` between services (indexes into `services`, in `search.json` order) and other targets (built-in, outside, unresolved, dynamic); loaded on the first graph view |
| `data/overview.json` | the server overview description and the packages left out of the analysis |
| `data/packages/<id>.json` | one package: services, entry points, calls into and from other packages, own data effects, overview |
| `data/services/<id>.json` | one service: identity, analysis coverage and findings, source path, signature, calls with status and evidence, callers, entry points, data effects (with how each is known), document types used, adapter configuration, description |

- Models: `src/wm_doc/explorer/contract.py`. JSON Schema:
  `docs/contracts/explorer.v1.schema.json` (`uv run python -m wm_doc.explorer.contract`).
  TypeScript types are generated from the schema (`npm run gen:contract`).
- IDs are 16 hex characters of a sha256 of the package and name: names differing only in
  case would collide as Windows file names. The app looks names up in `search.json` and only
  ever fetches by ID.
- Call status: `resolved` (an analysed service), `platform` (`pub.*`/`wm.*`), `outside` (a
  service name not among the analysed packages), `unresolved`, `dynamic` (target computed at
  run time) and `unsupported`. The classification is shared with focused publication
  (`wm_doc/call_targets.py`).
- Output is deterministic: sorted keys, compact JSON, no timestamps or absolute paths.
- The graph walk in the app uses only edges from `graph.json`; it never matches names. A
  test checks it reaches exactly the services focused publication reaches for the same
  service and depth (`explorer-ui/src/domain/graph-fixture.json`, generated by
  `tests/fixtures/test_explorer_graph.py`; regenerate with
  `WM_DOC_UPDATE_FIXTURES=1 uv run pytest tests/fixtures/test_explorer_graph.py`).
  Dynamic and unsupported calls get one target node per calling service, so they never
  look like a hub.
- Excluded: literal values, designer comments, Notes, the facts block, headings people added
  to a description, SQL, connection properties, absolute paths. A data effect known from a
  literal (for example the URL of an HTTP call) shows `(literal, not exported)` in place of
  the value; mapped pipeline paths are kept.
- Text is a list of plain segments (`text`, or `code` with the ID of the analysed service it
  names exactly); it is never HTML or Markdown. Model and human text (descriptions, finding
  messages, purpose lines) passes the disclosure scan; text that fails it is withheld and
  counted in `manifest.disclosure.withheldStrings`.
- Description states match `wm-doc status`: approved, stale (approved, facts changed),
  draft, edited. Only the Purpose, Usage, What it does to data, Main steps, Detailed flow and
  Error handling sections are exported.
- Optional fields may be added within v1; removing or renaming anything is v2. The app shows an
  error page for another contract version.

## Scale

Measured on synthetic packages of about 7,300 services and 9,600 document types (the size
of the production server), after analysis:

| What | Measured | Budget |
| --- | --- | --- |
| Export (facts, build, write) | about 12 s | 30 s |
| Memory for the export | about 270 MB | 300 MB |
| All data files | 27 MB | 30 MB |
| `search.json` / `graph.json` | 1.1 MB / 0.7 MB | 2 MB each |
| JavaScript (compressed) | 110 KB, plus 77 KB for the graph on service pages | 250 KB |

In the browser at that size (`npm run e2e:scale`, Chromium, served by `wm-doc explorer serve`
without compression):

| What | Measured | Budget |
| --- | --- | --- |
| Data and code loaded at start | 1.5 MB | 3 MB |
| Search usable after opening the page | about 1.1 s | 1.5 s |
| Search per keystroke, input to painted frame (95th percentile) | about 30 ms | 100 ms |
| Opening a service from search | about 150 ms | 300 ms |
| Call graph of a service with 7,300 callers | under 1 s, 28 nodes | 2 s |

Analysis itself is not part of these numbers: it takes minutes on a fresh run and is cached
afterwards.

## Security

- Every string is rendered as text by React; there is no HTML or Markdown rendering path, and
  lint rules forbid `dangerouslySetInnerHTML`, `innerHTML`, `eval` and script URLs.
- `index.html` carries a Content Security Policy (`script-src 'self'`, `connect-src 'self'`,
  no inline scripts); `explorer serve` also sends it as a header with `nosniff`.
- The app loads nothing from the internet (checked by tests).

## Developing the app

The app lives in `explorer-ui/` (React, TypeScript, Vite). Node.js 22 or later is needed only
here.

```bash
cd explorer-ui
npm ci --ignore-scripts
npm run check        # contract types, formatting, type check, lint, unit tests
npm run build        # writes src/wm_doc/explorer/app (committed)
npx playwright install chromium
npm run e2e          # builds a demo with wm-doc and runs the browser tests (incl. axe)
npm run e2e:scale    # browser budgets on ~7,300 synthetic services (first run: minutes)
```

For live development, build demo data once (`uv run wm-doc explorer demo -o
out/explorer-dev`) and run `npm run dev`.

After changing `explorer-ui/src`, run `npm run build` and commit the regenerated
`src/wm_doc/explorer/app` with the change; the build is reproducible, so an unchanged source
gives an unchanged bundle.
