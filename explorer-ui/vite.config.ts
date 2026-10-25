import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The built app ships inside the Python package; `wm-doc explorer build` copies it next to
// the data. In development, `npm run dev` serves the data of an explorer folder built by
// `wm-doc explorer demo -o ../out/explorer-dev` (or EXPLORER_DIR).
const appDir = fileURLToPath(new URL("../src/wm_doc/explorer/app", import.meta.url));
const devData = process.env.EXPLORER_DIR ?? fileURLToPath(new URL("../out/explorer-dev", import.meta.url));

export default defineConfig(({ command }) => ({
  base: "./",
  plugins: [react()],
  publicDir: command === "serve" ? devData : false,
  build: {
    outDir: appDir,
    emptyOutDir: true,
    assetsDir: "assets",
    sourcemap: false,
    target: "es2022",
  },
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    environment: "node",
  },
}));
