import { type ChildProcess, spawn, spawnSync } from "node:child_process";
import { existsSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";

import { SEEDED } from "./database.js";

const WEB_ROOT = fileURLToPath(new URL("../../../../", import.meta.url));
const hasBun = spawnSync("bun", ["--version"]).status === 0;

function env(extra: Record<string, string> = {}): NodeJS.ProcessEnv {
  const { DATABASE_URL: _database, NODE_ENV: _node, ...rest } = process.env;
  return { ...rest, ...extra };
}

/** Start preview through the package script used by `mise run web:preview`. */
function launch(port: number, extra: Record<string, string> = {}) {
  return spawn("bun", ["run", "serve:preview", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: WEB_ROOT,
    env: env(extra),
    stdio: ["ignore", "pipe", "pipe"],
  });
}

async function freePort(): Promise<number> {
  const server = createServer();
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as { port: number };
  await new Promise((resolve) => server.close(resolve));
  return port;
}

function exited(child: ChildProcess): Promise<{ code: number | null; output: string }> {
  return new Promise((resolve) => {
    let output = "";
    child.stdout?.on("data", (chunk) => (output += chunk));
    child.stderr?.on("data", (chunk) => (output += chunk));
    child.on("exit", (code) => resolve({ code, output }));
  });
}

describe.skipIf(!hasBun)("preview mode refuses to start", () => {
  it("under NODE_ENV=production", async () => {
    const { code, output } = await exited(launch(await freePort(), { NODE_ENV: "production" }));
    expect(code).toBe(1);
    expect(output).toMatch(/NODE_ENV=production/);
  });

  it("with a DATABASE_URL set", async () => {
    const { code, output } = await exited(
      launch(await freePort(), { DATABASE_URL: "postgres://app@db.example/tsdhn" }),
    );
    expect(code).toBe(1);
    expect(output).toMatch(/DATABASE_URL/);
  });
});

describe.skipIf(!hasBun)("preview mode in a checkout with a .env file", () => {
  const dotenv = join(WEB_ROOT, ".env.local");
  const saved = existsSync(dotenv) ? readFileSync(dotenv) : null;
  let server: ChildProcess;

  beforeAll(() => {
    writeFileSync(dotenv, "DATABASE_URL=postgres://app:secret@127.0.0.1:1/tsdhn\n");
  });

  afterAll(async () => {
    if (saved) writeFileSync(dotenv, saved);
    else rmSync(dotenv, { force: true });
    if (!server) return;
    const done = exited(server);
    server.kill("SIGTERM");
    await done;
  });

  it("ignores the file's DATABASE_URL and serves /login", async () => {
    const port = await freePort();
    server = launch(port);
    await vi.waitFor(
      async () => {
        const response = await fetch(`http://127.0.0.1:${port}/login`, { redirect: "manual" });
        expect(response.status).toBe(200);
      },
      { timeout: 90_000, interval: 500 },
    );
  }, 120_000);
});

describe.skipIf(!hasBun)("preview mode served", () => {
  let server: ChildProcess;
  let base: string;
  let cookie = "";

  const get = (path: string, init: RequestInit = {}) =>
    fetch(`${base}${path}`, { redirect: "manual", ...init, headers: { cookie, ...init.headers } });

  beforeAll(async () => {
    const port = await freePort();
    base = `http://127.0.0.1:${port}`;
    server = launch(port);
    await vi.waitFor(
      async () => {
        const first = await fetch(`${base}/simulations`, { redirect: "manual" });
        expect(first.status).toBe(200);
        cookie = first.headers
          .getSetCookie()
          .map((line) => line.split(";")[0])
          .join("; ");
      },
      { timeout: 90_000, interval: 500 },
    );
  }, 120_000);

  afterAll(async () => {
    const done = exited(server);
    server.kill("SIGTERM");
    await done;
  });

  it("signs the demo user in on the first request", () => {
    expect(cookie).toMatch(/session_token/);
  });

  it("serves the list and the form", async () => {
    const paths = ["/simulations", "/new", `/new?from=${SEEDED[0].id}`];
    const statuses = await Promise.all(paths.map(async (path) => (await get(path)).status));
    expect(statuses).toEqual([200, 200, 200]);
    expect((await get("/")).headers.get("location")).toBe("/simulations");
  });

  it("serves the signed-out forms to a client with no session", async () => {
    const paths = ["/login", "/signup"];
    const statuses = await Promise.all(
      paths.map(async (path) => (await fetch(`${base}${path}`, { redirect: "manual" })).status),
    );
    expect(statuses).toEqual([200, 200]);
  });

  it("shows a queued, a running, a completed, a failed and an unsent simulation", async () => {
    const labels = ["Lista", "En curso", "En cola", "Falló", "No se envió", "Lista"];
    const pages = await Promise.all(
      SEEDED.map(async ({ id }) => {
        const response = await get(`/simulations/${id}`);
        return { status: response.status, html: await response.text() };
      }),
    );
    expect(pages.map((page) => page.status)).toEqual(labels.map(() => 200));
    pages.forEach((page, index) => expect(page.html).toContain(labels[index]));
  });

  it("signs out and back in with the demo credentials", async () => {
    const first = await fetch(`${base}/simulations`, { redirect: "manual" });
    const own = first.headers
      .getSetCookie()
      .map((line) => line.split(";")[0])
      .join("; ");
    const headers = { cookie: own, origin: base };

    const signOut = await fetch(`${base}/api/auth/sign-out`, {
      method: "POST",
      headers: { ...headers, "content-type": "application/json" },
      body: "{}",
    });
    expect(signOut.status).toBe(200);
    expect((await fetch(`${base}/login`, { redirect: "manual", headers })).status).toBe(200);

    const signIn = await fetch(`${base}/login`, {
      method: "POST",
      redirect: "manual",
      headers: { ...headers, accept: "text/html" },
      body: new URLSearchParams({ email: "demo@tsdhn.test", password: "demo-preview" }),
    });
    expect(signIn.status).toBe(303);
    expect(signIn.headers.getSetCookie().join()).toMatch(/session_token/);
  });

  it("answers 404 for an unknown simulation and an unknown page", async () => {
    expect((await get(`/simulations/${crypto.randomUUID()}`)).status).toBe(404);
    expect((await get("/nothing-here")).status).toBe(404);
  });

  it("relays progress from the stub", async () => {
    const response = await get(`/simulations/${SEEDED[1].id}/events`, {
      signal: AbortSignal.timeout(10_000),
    });
    expect(response.status).toBe(200);
    const reader = response.body!.getReader();
    const { value } = await reader.read();
    await reader.cancel();
    const frame = JSON.parse(new TextDecoder().decode(value).replace(/^data: /, ""));
    expect(frame).toMatchObject({ status: "running", step: "tsunami", step_index: 3 });
  });

  it("redirects a download to a file the stub serves", async () => {
    const redirect = await get(`/simulations/${SEEDED[0].id}/outputs/max_height_map`);
    expect(redirect.status).toBe(302);
    const file = await get(redirect.headers.get("location")!);
    expect(file.status).toBe(200);
    expect(file.headers.get("content-type")).toBe("application/pdf");
  });

  it("estimates through the stub and queues a submitted simulation", async () => {
    const values = {
      magnitude: 8.2,
      depth: 20,
      latitude: -15,
      longitude: -76,
      datetime: "2026-10-10T12:30",
    };
    const estimate = await get("/api/calculations", {
      method: "POST",
      headers: { "content-type": "application/json", origin: base },
      body: JSON.stringify(values),
    });
    expect(estimate.status).toBe(200);
    expect((await estimate.json()).calculation.tsunami_warning).toBeTruthy();

    const submitted = await get("/new", {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded", origin: base },
      body: new URLSearchParams(Object.entries(values).map(([k, v]) => [k, String(v)])),
    });
    expect(submitted.status).toBe(200);

    const list = await (await get("/simulations")).text();
    expect(list.match(/En cola/g)?.length).toBeGreaterThanOrEqual(2);
  });
});
