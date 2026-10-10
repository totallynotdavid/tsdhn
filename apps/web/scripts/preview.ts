import { parseArgs } from "node:util";

import { DEMO_USER } from "../src/lib/server/preview/canned.ts";

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

// The package script disables Bun's `.env` loading. These checks inspect the
// caller's shell environment, so a DATABASE_URL here is the caller's value.
if (process.env.NODE_ENV === "production") {
  console.error("Preview mode refuses to run with NODE_ENV=production.");
  process.exit(1);
}
if (process.env.DATABASE_URL?.trim()) {
  console.error(
    "Preview mode refuses to run with DATABASE_URL set; it uses its own embedded database.",
  );
  process.exit(1);
}

// Pass only these shell variables to the app. The launcher generates the
// remaining secrets, so caller credentials do not cross the boundary.
const INHERITED = ["PATH", "HOME", "USER", "TMPDIR", "TERM", "LANG", "LC_ALL", "NO_COLOR"];
const inherited = Object.fromEntries(
  INHERITED.flatMap((name) => (process.env[name] === undefined ? [] : [[name, process.env[name]]])),
);

const randomHex = () => Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString("hex");
const child = Bun.spawn(
  [
    "bun",
    "--no-env-file",
    "run",
    "dev",
    "--host",
    values.host,
    "--port",
    String(port),
    "--strictPort",
  ],
  {
    env: {
      ...inherited,
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
