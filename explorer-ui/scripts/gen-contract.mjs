// Generate src/contract/explorer-v1.ts from docs/contracts/explorer.v1.schema.json.
// The schema itself is generated from the pydantic models in wm_doc.explorer.contract, so the
// Python and TypeScript sides cannot drift. `--check` fails when the committed file is stale.
import { readFile, writeFile } from "node:fs/promises";

import { compile } from "json-schema-to-typescript";

const schemaUrl = new URL("../../docs/contracts/explorer.v1.schema.json", import.meta.url);
const outputUrl = new URL("../src/contract/explorer-v1.ts", import.meta.url);
const banner =
  "/* Generated from docs/contracts/explorer.v1.schema.json by scripts/gen-contract.mjs.\n" +
  " * Do not edit: change wm_doc/explorer/contract.py, then regenerate both. */";

// Property titles ("Disabledsteps") would become named type aliases; only $defs keep theirs.
function stripTitles(node, keep) {
  if (Array.isArray(node)) return node.map((item) => stripTitles(item, false));
  if (node === null || typeof node !== "object") return node;
  const out = {};
  for (const [key, value] of Object.entries(node)) {
    if (key === "title" && !keep) continue;
    if (key === "$defs") {
      out[key] = Object.fromEntries(
        Object.entries(value).map(([name, def]) => [name, stripTitles(def, true)]),
      );
    } else {
      out[key] = stripTitles(value, false);
    }
  }
  return out;
}

const schema = stripTitles(JSON.parse(await readFile(schemaUrl, "utf8")), false);
const root = {
  ...schema,
  title: "ExplorerContractFiles",
  type: "object",
  additionalProperties: false,
  properties: {
    manifest: { $ref: "#/$defs/Manifest" },
    search: { $ref: "#/$defs/SearchIndex" },
    service: { $ref: "#/$defs/ServiceDetail" },
  },
  required: ["manifest", "search", "service"],
};
const generated = await compile(root, "ExplorerContractFiles", {
  bannerComment: banner,
  additionalProperties: false,
  unreachableDefinitions: true,
  strictIndexSignatures: true,
  style: { printWidth: 100, singleQuote: false, trailingComma: "all" },
});
const text = generated.replace(/\r\n/g, "\n");

if (process.argv.includes("--check")) {
  const committed = (await readFile(outputUrl, "utf8").catch(() => "")).replace(/\r\n/g, "\n");
  if (committed !== text) {
    console.error("src/contract/explorer-v1.ts is stale: run `npm run gen:contract`.");
    process.exit(1);
  }
} else {
  await writeFile(outputUrl, text, "utf8");
}
