import { defineConfig, devices } from "@playwright/test";

// The E2E tests run the shipped app (src/wm_doc/explorer/app, so `npm run build` first) on
// synthetic demo data, served exactly as users serve it: `wm-doc explorer serve`.
const PORT = 8799;
const wmDoc = process.env.WM_DOC ?? "uv run wm-doc";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${String(PORT)}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command:
      `${wmDoc} explorer demo -o .e2e/explorer --services 40 && ` +
      `${wmDoc} explorer serve .e2e/explorer --port ${String(PORT)}`,
    url: `http://127.0.0.1:${String(PORT)}/data/manifest.json`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
