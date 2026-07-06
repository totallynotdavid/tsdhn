import { defineConfig } from "oxlint";

export default defineConfig({
  plugins: ["typescript", "import", "promise"],
  categories: {
    correctness: "error",
    suspicious: "warn",
    perf: "warn",
  },
  env: {
    browser: true,
    node: true,
    es2024: true,
  },
  rules: {
    "import/no-unassigned-import": "off",
  },
  overrides: [
    {
      files: ["**/*.svelte"],
      rules: {
        "no-unassigned-vars": "off",
      },
    },
  ],
  ignorePatterns: [
    "**/node_modules/**",
    "**/.svelte-kit/**",
    "**/build/**",
    "**/dist/**",
    "**/.venv/**",
    "libs/api-client/src/generated/**",
  ],
});
