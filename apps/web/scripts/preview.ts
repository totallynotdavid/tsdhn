import { parseArgs } from "node:util";

import { DEMO_USER } from "../src/lib/server/preview/canned.ts";
import { previewRefusal } from "../src/lib/server/preview/guard.ts";

const { values } = parseArgs({
  options: {
    host: { type: "string", default: "0.0.0.0" },
    port: { type: "string", default: "5174" },
  },
});

const port = Number(values.port);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  console.error(`Invalid port: ${values.port}`);
  process.exit(1);
}

const refusal = previewRefusal(process.env);
if (refusal) {
  console.error(refusal);
  process.exit(1);
}

const randomHex = () => Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString("hex");
const child = Bun.spawn(
  ["bun", "run", "dev", "--host", values.host, "--port", String(port), "--strictPort"],
  {
    env: {
      ...process.env,
      TSDHN_PREVIEW: "1",
      ORIGIN: `http://localhost:${port}`,
      COMPUTE_API_URL: `http://127.0.0.1:${port}/_preview/compute`,
      COMPUTE_API_TOKEN: randomHex(),
      BETTER_AUTH_SECRET: randomHex(),
    },
    stdio: ["inherit", "inherit", "inherit"],
  },
);

console.log("Preview mode: embedded database, stub compute API.");
console.log(`Signed in as ${DEMO_USER.email}; the password is ${DEMO_USER.password}.`);

for (const signal of ["SIGINT", "SIGTERM"] as const) process.on(signal, () => child.kill(signal));
process.exit(await child.exited);
