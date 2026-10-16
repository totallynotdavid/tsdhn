import { bindings, defineConfig } from "cf/config";
import * as entrypoint from "./src/index.ts" with { type: "cf-worker" };

export default defineConfig({
  worker: {
    name: "tsdhn",
    compatibilityDate: "2026-10-01",
    entrypoint,
    observability: { enabled: true, logs: { enabled: true, invocationLogs: false } },
    env: { WEB: bindings.vpcService({ id: "01a1462e-3c1c-7941-8d35-14f7ef95bcda" }) },
  },
});
