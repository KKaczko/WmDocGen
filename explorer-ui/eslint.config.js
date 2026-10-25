import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

// Package-derived text is untrusted: no HTML injection APIs, no eval, no script URLs.
const noHtmlInjection = {
  "react/no-danger": "error",
  "react/no-danger-with-children": "error",
  "react/jsx-no-script-url": "error",
  "react/jsx-no-target-blank": "error",
  "no-eval": "error",
  "no-implied-eval": "error",
  "no-new-func": "error",
  "no-restricted-properties": [
    "error",
    { property: "innerHTML", message: "Render text with React; never inject HTML." },
    { property: "outerHTML", message: "Render text with React; never inject HTML." },
    { property: "insertAdjacentHTML", message: "Render text with React; never inject HTML." },
    { object: "document", property: "write", message: "Never write HTML into the page." },
  ],
};

export default tseslint.config(
  { ignores: ["node_modules", "playwright-report", "test-results", ".e2e", "src/contract/explorer-v1.ts"] },
  js.configs.recommended,
  ...tseslint.configs.strict,
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: { globals: globals.browser },
    settings: { react: { version: "detect" } },
    plugins: { react, "react-hooks": reactHooks, "jsx-a11y": jsxA11y },
    rules: {
      ...react.configs.recommended.rules,
      ...react.configs["jsx-runtime"].rules,
      ...reactHooks.configs.recommended.rules,
      ...jsxA11y.configs.strict.rules,
      ...noHtmlInjection,
    },
  },
  {
    files: ["*.ts", "*.js", "scripts/**/*.mjs", "e2e/**/*.ts"],
    languageOptions: { globals: globals.node },
  },
);
