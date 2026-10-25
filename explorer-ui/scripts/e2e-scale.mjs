// Browser checks at production size: about 7,300 services and 9,600 document types.
// The first run generates the synthetic packages and analyses them (several minutes); later
// runs reuse them and the analysis cache, and only rebuild the explorer.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";

const wmDoc = process.env.WM_DOC ?? "uv run wm-doc";
const shell = process.platform === "win32";

function run(command, env = process.env) {
  console.log(`> ${command}`);
  const result = spawnSync(command, { stdio: "inherit", shell: shell ? true : "/bin/sh", env });
  if (result.status !== 0) process.exit(result.status ?? 1);
}

if (!existsSync(".e2e/scale-packages")) {
  run(
    `${wmDoc} explorer demo -o .e2e/scale --services 7285 --documents 9600 ` +
      "--packages-dir .e2e/scale-packages",
  );
} else {
  run(
    `${wmDoc} explorer build .e2e/scale-packages -o .e2e/scale --dataset-kind synthetic ` +
      '--dataset-label "Synthetic scale data"',
  );
}
run("npx playwright test --project scale", { ...process.env, WM_DOC_E2E_SCALE: "1" });
