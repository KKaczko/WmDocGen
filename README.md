# wm-doc

`wm-doc` documents webMethods Integration Server packages (built against 10.15) by reading the
package files offline. It never connects to Integration Server, never runs package code and
never changes the packages.

It produces two things:

- **A technical documentation site** (`wm-doc analyze`): one Markdown page per package,
  service and document type, dependency graphs, an index, and for every service a summary, its
  signature, every call (FLOW steps, transformers and Java), who calls it, which entry points
  reach it, and which data objects and systems it touches. Each package page lists the
  package's entry points, services, data and systems, and the packages it calls.
- **One reviewed description file per service** (`wm-doc describe`): a short text drafted by a
  local language model from the facts above, saying what the service is for, who uses it, what
  it does to which data and where, its main steps and error handling, plus a plain-text comment
  ready to paste into the service's Comments field in Designer. You review, edit and approve
  these files; approved text is never overwritten.
- **Package and server overviews** (`wm-doc overview`): the same kind of reviewed file for each
  package and for the whole server, drafted from the package facts and the services' Purpose
  lines.

The model only words facts the tool has already established. Every name in its answer must
appear in those facts, or the answer is rejected.

## Install

Python 3.12+ and [`uv`](https://docs.astral.sh/uv/):

```powershell
uv sync
uv run wm-doc --help
```

Graphviz (`dot`) is optional and only needed for `--render-graphs`. An Ollama server is needed
only for `describe` and `overview`.

## Documenting a server, step by step

Point the commands at the server's `packages` directory, or a copy of it.

1. **See what is there.** `stats` prints counts and names (no code or values): packages, services
   by kind, disabled FLOW steps, artifact types, FLOW elements the parser does not interpret
   yet, every platform service missing from the catalog, calls leaving the analysed packages
   (and whether their targets exist in the folder as something other than a service), and the
   largest services.

   ```powershell
   wm-doc stats D:\IntegrationServer\instances\default\packages --output stats.md
   ```

   Product packages (`Wm*`), `Default` and packages marked `system_package=yes` are skipped by
   default; see `--include-package`, `--exclude-package`, `--all-packages` or a config file
   (`examples/wm-doc.yml`).

   The first run analyses every package, which takes minutes on a large server. Later runs of
   any command reuse that analysis while no package file has changed (about a second); see
   [Analysis cache](#analysis-cache).

2. **Declare what the code calls but does not contain.** Copy `examples/external-systems.yml`
   and map namespace patterns from the stats report to system names. Optionally list your
   business processes in `processes.yml` (see `docs/format-behavior.md`).

   Platform services (`pub.*`, `wm.*` from WmPublic, WmART, WmJDBCAdapter, ...) are described
   by a catalog shipped with the tool (`src/wm_doc/data/platform_services.yml`, about 660
   services: every service in the Integration Server 10.15 Built-In Services Reference, plus the
   WmJDBCAdapter, EDI and `wm.server.*` services seen in real packages). If `stats` lists some as missing, describe them in your own file (see
   `examples/platform-services.yml`) and pass it with `--platform-services` to `stats`,
   `analyze`, `describe`, `overview` and `status`. A changed description changes the facts:
   unapproved drafts are redrafted, and approved ones show as "approved, facts changed".

3. **Check the model server.**

   ```powershell
   $env:OLLAMA_API_KEY = "<token>"   # only for a server behind an authenticating proxy
   wm-doc provider-probe --url https://server/ollama --api-key-env OLLAMA_API_KEY --allow-remote-provider --model qwen3.8:27b
   ```

   It reports whether the proxy forwards Ollama's native API or only the OpenAI-compatible
   `/v1` API, the model's context length, and the exact flags to use.

4. **Describe a pilot package.**

   ```powershell
   wm-doc describe D:\...\packages --package OrdersCore --with-callees --model qwen3.8:27b --docs-dir service-docs --external-systems external-systems.yml
   ```

   Besides a short list of main steps, each description has a detailed flow: every call in
   order, the system or table behind it, which inputs it gets and where they come from, and
   what it returns to later steps (from the outputs the called service declares). Naming the
   systems behind other namespaces in `external-systems.yml` makes this flow say which
   application each call goes to.

   Selection: `--service` (repeatable), `--namespace`, `--package` or `--all`. Services are
   described callees first; each caller's prompt includes the Purpose line of every service it
   calls. Each file is written as soon as it is validated, so an interrupted run continues where
   it stopped. Use `--parallel N` if the server runs several requests at once.

5. **Review and approve.** Edit the files under `service-docs/` as needed, then:

   ```powershell
   wm-doc approve --docs-dir service-docs --service orders.api:createOrder
   wm-doc approve --docs-dir service-docs --package OrdersCore
   wm-doc status D:\...\packages --docs-dir service-docs     # writes service-docs/STATUS.md
   ```

6. **Write package and server overviews** once a package's services are described (the
   overview prompt uses their Purpose lines, approved text first; services without a
   description use their generated summary).

   ```powershell
   wm-doc overview D:\...\packages --package OrdersCore --model qwen3.8:27b --docs-dir service-docs --external-systems external-systems.yml
   wm-doc overview D:\...\packages --all --server --model qwen3.8:27b --docs-dir service-docs
   wm-doc approve --docs-dir service-docs --service package:OrdersCore
   wm-doc approve --docs-dir service-docs --service server
   ```

   `--package` is repeatable; `--all` takes every analysed package. `--server` writes the server
   overview after the package overviews, from their Purpose lines. Package facts that do not
   fit `--num-ctx` are shortened (the service list first) and reported.

7. **Publish.**

   ```powershell
   wm-doc analyze D:\...\packages --output site --docs-dir service-docs --external-systems external-systems.yml --render-graphs svg
   wm-doc export-comments --docs-dir service-docs --output designer-comments
   ```

   Service and package pages show their description with its review status, and `index.md`
   shows the server overview and a table of packages. `service-catalogue.md` lists every
   service's purpose. `designer-comments/<Package>.txt` holds the comment texts to paste into
   Designer. With `--render-graphs`, every service page also gets a call graph: the service, the
   services it calls (two levels; platform helpers folded into one node), the systems and data
   it touches, and the services and entry points that reach it.

8. **Keep it current.** After code changes, run `describe` and `overview` again: unchanged
   drafts are kept, changed drafts are regenerated, and approved or edited texts are kept while
   their facts block is refreshed. `status` lists approved texts whose facts have changed so you
   can review them. Rewording a service description does not mark its package overview as
   changed; use `overview --redo-drafts` to redraft unapproved overviews from new Purpose lines.

## Description files

`service-docs/<Package>/<namespace folders>/<service>.md`:

```markdown
---
service: orders.api:createOrder
package: OrdersCore
status: draft            # draft | approved
model: qwen3.8:27b
facts_hash: 3f9c...      # facts the text was written from or approved against
text_hash: a81b...       # the text as generated; a different hash means you edited it
---
# createOrder
## Purpose / ## Usage / ## What it does to data / ## Main steps
## Detailed flow        (every call in order: system, inputs and where they come from, outputs)
## Error handling
## Designer comment      (plain text, at most 600 characters)
## Notes                 (yours; the tool never writes here)
<!-- wm-doc:facts:start hash=... -->
## Facts                 (Used by, Inputs and outputs, Data and systems touched; always refreshed)
<!-- wm-doc:facts:end -->
```

Overviews use the same format: `service-docs/<Package>/_package.md` (`service: package:<Package>`,
sections Purpose, Main capabilities, Entry points, Systems and data) and `service-docs/_server.md`
(`service: server`, with Business areas instead of Main capabilities). Their facts block holds
the package or server facts the draft was written from.

- An answer that names something the facts do not contain is rejected after one retry. With
  `describe --keep-unverified` it is written anyway as a draft marked with those names
  (`unverified_names` in the front matter and a notice at the top); it is asked again on the
  next run until it passes, and approving it removes the mark. Answers that fail the
  disclosure scan are never kept.
- A draft you edited, or an approved file, is never regenerated. To get a fresh draft, set
  `status: draft` and restore or delete the text, or delete the file.
- `--redo-drafts` regenerates unedited drafts even when their facts did not change.
- Files contain no timestamps; the same inputs give the same files.

## Where the facts come from

Everything below is read from package files. Each "data and systems" row says how it is known.

| Fact | Source |
| --- | --- |
| Calls | FLOW `INVOKE` and transformer (`MAPINVOKE`) steps; statically confirmed Java `Service.doInvoke` calls. Steps marked disabled in Designer are left out and counted |
| Signatures | `node.ndf`, or the specification named by `svc_spec` |
| Error handling | TRY/CATCH, try/catch sequences, REPEAT on failure, EXIT with failure, `pub.flow:getLastError` (FLOW only; Java and opaque services say "not analysed") |
| Platform service calls | the platform catalog (shipped, plus `--platform-services`): a one-line description and an effect family |
| Published documents, HTTP/REST/SOAP endpoints, LDAP entries, JMS destinations, files, FTP/SFTP, email, storage | the documented input field of the platform service, when the FLOW sets it as a literal or maps it from the pipeline |
| JDBC adapter services | operation template, tables and connection, decoded from the service's configuration; the connection's database product, database name and transaction type. Server, port, user, password, URL and SQL are never read |
| Other opaque services | name, signature, and connections their `node.ndf` names |
| Entry points | triggers (JMS or webMethods messaging, with their queues, topics, JMS alias and subscribed documents, and the JDBC adapter notification that publishes a subscribed document), REST/SOAP descriptors and other artifacts whose `node.ndf` contains a service's exact name; legacy REST v1 handlers (`_get`, `_post`, ... at `/rest/<namespace as path>`); `processes.yml`; callers that nothing calls |
| External systems | `external-systems.yml` namespace patterns |
| Developer comments | `<COMMENT>` text in `flow.xml` (used in prompts, subject to the free-text policy) |

Not interpreted: SQL text, trigger filters and message selectors, other adapter types'
configuration, REST v2 resource paths, scheduler entries, and Java control flow.
`wm-doc probe-shapes` prints the key layout of such artifacts (key names and counts, no values)
so these can be added later from real shapes.

For adapter and other opaque services, `describe` lets the model word only the purpose, usage,
data effects and Designer comment; the tool writes the Main steps (the configured adapter
operation, or "Not analysed") and the error handling ("not analysed").

## Commands

| Command | Purpose |
| --- | --- |
| `stats` | Counts and names to plan the work |
| `analyze` | Technical documentation site (`--docs-dir` adds descriptions; `--verbose` adds mapping and FLOW detail; `--target-*` publishes a focused subset) |
| `describe` | Draft or refresh service description files with a model |
| `overview` | Draft or refresh package overviews and the server overview with a model |
| `approve` | Mark descriptions approved (`--service package:<P>` or `--service server` for overviews) |
| `status` | Report missing, draft, edited, approved and outdated descriptions and overviews |
| `export-comments` | Designer comment texts per package |
| `provider-probe` | Check how a model server can be reached |
| `probe-shapes` | Key layout of triggers, descriptors and adapter services (no values) |
| `scan` | Package and artifact inventory only |

## Safety

- Package files are only read, with a hardened XML parser (no DTDs or entities).
- Secret-like literals and comments are redacted in every output; `--config` can redact or omit
  all literals or free text.
- Prompts and raw model responses are never stored; only validated text is cached
  (`--cache-dir`, default under your user cache folder).
- A server token is read from an environment variable (`--api-key-env`), never from a flag, and
  is only sent over https or to a loopback address.

## Output reference

`wm-doc analyze` writes `analysis.json` (schema `analysis.v11`; each fact is stored once, on
the service, package or document it belongs to), `index.md`, `LIMITATIONS.md`,
`entrypoints.md`, `artifacts.md`, `platform-services.md` (platform services the code calls,
with their descriptions and callers), `packages/*.md`, `services/*.md`, `documents/*.md`,
`graphs/*.dot` and `graphs/index.md`, `processes/*.md` when processes are declared,
`service-catalogue.md` with `--docs-dir`, and with `--render-graphs` SVG/PNG graphs plus one call
graph per service (`graphs/services/`). Before writing it removes only these generated files and
directories; other files in the output directory are kept.

## Analysis cache

`stats`, `analyze`, `describe`, `overview`, `status` and `probe-shapes` start from a full
analysis of the packages directory. The result is cached (gzip-compressed, one entry per
packages directory and configuration) and reused while the tool version, the configuration, the
`processes.yml` file and every package file (path, size, modification time) are unchanged; any
change triggers a fresh analysis. The cache lives under `%LOCALAPPDATA%\wm-doc\analysis-cache`
(or `~/.cache/wm-doc/analysis-cache`); set `WM_DOC_ANALYSIS_CACHE_DIR` to move it, or pass
`--no-analysis-cache` to analyse from scratch. It holds the same data as `analysis.json`, so keep
it where `analysis.json` may be kept.

Architecture and format details: `docs/architecture.md`, `docs/format-behavior.md`,
`docs/unsupported-constructs.md`.

## Development

```powershell
uv run pytest
uv run ruff check .
uv run mypy
```
