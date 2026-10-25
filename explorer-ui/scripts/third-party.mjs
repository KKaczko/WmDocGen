// Write THIRD-PARTY.txt next to the built app: the name, version, licence and licence text of
// every package that ends up in the bundle (runtime dependencies in package-lock.json).
import { readdir, readFile, writeFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const outFile = new URL("../src/wm_doc/explorer/app/THIRD-PARTY.txt", root);
const lock = JSON.parse(await readFile(new URL("package-lock.json", root), "utf8"));

const runtime = Object.entries(lock.packages)
  .filter(([path, info]) => path.startsWith("node_modules/") && !info.dev && !info.devOptional)
  .map(([path, info]) => ({ path, name: path.slice(path.lastIndexOf("node_modules/") + 13), info }))
  .sort((a, b) => (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));

const sections = [
  "Third-party software bundled in the WmDocGen Explorer app.",
  "",
];
for (const { path, name, info } of runtime) {
  const dir = new URL(`${path}/`, root);
  const files = await readdir(dir).catch(() => []);
  const licenceFile = files.filter((file) => /^(licen[cs]e|copying)/i.test(file)).sort()[0];
  const text = licenceFile
    ? (await readFile(new URL(licenceFile, dir), "utf8")).replace(/\r\n/g, "\n").trim()
    : "(no licence file in the package)";
  sections.push("=".repeat(78), `${name} ${info.version} (${info.license ?? "unknown"})`, "", text, "");
}
await writeFile(outFile, sections.join("\n"), "utf8");
console.log(`THIRD-PARTY.txt: ${runtime.length} package(s)`);
