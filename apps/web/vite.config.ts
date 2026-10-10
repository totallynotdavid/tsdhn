import { mdsvex } from "mdsvex";
import tailwindcss from "@tailwindcss/vite";
import adapterAuto from "@sveltejs/adapter-auto";
import adapterNode from "@sveltejs/adapter-node";
import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

const adapter = process.env.ADAPTER === "node" ? adapterNode() : adapterAuto();
const previewing = process.env.TSDHN_PREVIEW === "1";

export default defineConfig({
  // Preview takes variables from the launcher, not from `.env` files.
  // SvelteKit reads `env.dir`, so preview points it to an empty directory.
  envDir: previewing ? false : undefined,
  // Preview requests may use any host name on the network.
  server: previewing ? { allowedHosts: true } : {},
  plugins: [
    tailwindcss(),
    sveltekit({
      compilerOptions: {
        // Enable runes for project files, not for dependencies.
        runes: ({ filename }) =>
          filename.split(/[/\\]/).includes("node_modules") ? undefined : true,
      },
      adapter,
      env: previewing ? { dir: ".svelte-kit/no-env" } : {},
      preprocess: [mdsvex({ extensions: [".svx", ".md"] })],
      extensions: [".svelte", ".svx", ".md"],
    }),
  ],
});
