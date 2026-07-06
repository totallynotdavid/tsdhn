import { defineConfig } from "oxfmt";

export default defineConfig({
  ignorePatterns: [
    "**/.svelte-kit/**",
    "**/build/**",
    "**/dist/**",
    "model/**",
    "jobs/**",
    ".ruff_cache/**",
    ".pytest_cache/**",
    ".mypy_cache/**",
    "libs/api-client/src/generated/**",
    "libs/api-client/openapi.json",
  ],
});
