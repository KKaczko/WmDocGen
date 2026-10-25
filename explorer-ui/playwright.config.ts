import { defineConfig, devices } from "@playwright/test";

// The E2E tests run the shipped app (src/wm_doc/explorer/app, so `npm run build` first) on
// synthetic demo data, served exactly as users serve it: `wm-doc explorer serve`.
// `npm run e2e:scale` adds the "scale" project on 7,300 synthetic services.
const PORT = 8799;
const SCALE_PORT = 8798;
const wmDoc = process.env.WM_DOC ?? "uv run wm-doc";
const scale = process.env.WM_DOC_E2E_SCALE === "1";

export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  reporter: [["list"]],
  use: {
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      testIgnore: /scale\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], baseURL: `http://127.0.0.1:${String(PORT)}` },
    },
    ...(scale
      ? [
          {
            name: "scale",
            testMatch: /scale\.spec\.ts/,
            use: {
              ...devices["Desktop Chrome"],
              baseURL: `http://127.0.0.1:${String(SCALE_PORT)}`,
            },
          },
        ]
      : []),
  ],
  webServer: scale
    ? {
        command: `${wmDoc} explorer serve .e2e/scale --port ${String(SCALE_PORT)}`,
        url: `http://127.0.0.1:${String(SCALE_PORT)}/data/manifest.json`,
        reuseExistingServer: false,
        timeout: 60_000,
      }
    : {
        command:
          `${wmDoc} explorer demo -o .e2e/explorer --services 40 && ` +
          `${wmDoc} explorer serve .e2e/explorer --port ${String(PORT)}`,
        url: `http://127.0.0.1:${String(PORT)}/data/manifest.json`,
        reuseExistingServer: false,
        timeout: 180_000,
      },
});
