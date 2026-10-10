import { eq } from "drizzle-orm";
import { beforeAll, describe, expect, it } from "vitest";

import { simulation } from "#lib/server/db/schema.js";
import type { SimulationDatabase } from "#lib/server/simulation-repository.js";

import { COMPUTE_STUB_PREFIX, createComputeStub, FILES_PREFIX } from "./compute-stub.js";
import { createPreviewDatabase } from "./database.js";

const TOKEN = "stub-token";
const COMPLETED = "00000000-0000-4000-8000-000000000001";

let db: SimulationDatabase;
let stub: ReturnType<typeof createComputeStub>;

beforeAll(async () => {
  db = await createPreviewDatabase({});
  stub = createComputeStub({ db, token: TOKEN, stepMs: 2 });
});

function call(path: string, init: RequestInit = {}, token = TOKEN): Promise<Response> {
  return stub.handle(
    new Request(`http://stub.test${COMPUTE_STUB_PREFIX}${path}`, {
      ...init,
      headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
    }),
  );
}

const submit = (input: object) => {
  const simulation_id = crypto.randomUUID();
  return call("/api/v1/jobs", {
    method: "POST",
    body: JSON.stringify({ simulation_id, input }),
  }).then((response) => ({ response, simulation_id }));
};

/** Every frame of the progress stream, read until the stream closes. */
async function frames(simulationId: string): Promise<{ status: string; outputs: string[] }[]> {
  const response = await call(`/api/v1/jobs/${simulationId}/events`);
  const text = await response.text();
  return text
    .split("\n\n")
    .filter((part) => part.startsWith("data: "))
    .map((part) => JSON.parse(part.slice("data: ".length)));
}

describe("compute stub", () => {
  it("rejects a request without the token", async () => {
    const response = await call("/api/v1/calculations", { method: "POST", body: "{}" }, "wrong");
    expect(response.status).toBe(401);
  });

  it("estimates a source from the magnitude", async () => {
    const small = await call("/api/v1/calculations", {
      method: "POST",
      body: JSON.stringify({ Mw: 7.2, h: 20, lat0: -12, lon0: -78, dia: "10", hhmm: "1200" }),
    });
    const large = await call("/api/v1/calculations", {
      method: "POST",
      body: JSON.stringify({ Mw: 8.8, h: 20, lat0: -12, lon0: -78, dia: "10", hhmm: "1200" }),
    });
    const [a, b] = await Promise.all([small.json(), large.json()]);
    expect(b.calculation.length).toBeGreaterThan(a.calculation.length);
    expect(Object.keys(b.travel_times.arrival_times)).toContain("Callao");
  });

  it("queues a submitted simulation, then completes it with every output", async () => {
    const { response, simulation_id } = await submit({
      Mw: 8.2,
      h: 20,
      lat0: -15,
      lon0: -76,
      dia: "10",
      hhmm: "1230",
    });
    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({ simulation_id, status: "queued" });

    const seen = await frames(simulation_id);
    expect(seen.at(-1)?.status).toBe("completed");
    expect(seen.at(-1)?.outputs).toContain("max_height_map");
  });

  it("runs a simulation once when the same ID is submitted again", async () => {
    const input = { Mw: 8.2, h: 20, lat0: -15, lon0: -76, dia: "10", hhmm: "1230" };
    const { simulation_id } = await submit(input);
    const again = await call("/api/v1/jobs", {
      method: "POST",
      body: JSON.stringify({ simulation_id, input }),
    });
    expect(again.status).toBe(200);

    const seen = await frames(simulation_id);
    expect(seen.at(-1)?.status).toBe("completed");
    const statuses = seen.map((frame) => frame.status);
    expect(statuses.indexOf("completed")).toBe(statuses.length - 1);
  });

  it("rejects a repeated ID with different input", async () => {
    const input = { Mw: 8.2, h: 20, lat0: -15, lon0: -76, dia: "10", hhmm: "1230" };
    const { simulation_id } = await submit(input);
    const again = await call("/api/v1/jobs", {
      method: "POST",
      body: JSON.stringify({ simulation_id, input: { ...input, Mw: 7.1 } }),
    });
    expect(again.status).toBe(400);
    expect((await again.json()).detail).toMatch(/different input/);
  });

  it("leaves a finished seeded simulation as it is when it is submitted again", async () => {
    const [{ params }] = await db
      .select({ params: simulation.params })
      .from(simulation)
      .where(eq(simulation.id, COMPLETED));
    const again = await call("/api/v1/jobs", {
      method: "POST",
      body: JSON.stringify({ simulation_id: COMPLETED, input: params }),
    });
    expect(again.status).toBe(200);
    expect((await again.json()).status).toBe("completed");
    await new Promise((resolve) => setTimeout(resolve, 60));
    const seen = await frames(COMPLETED);
    expect(seen.map((frame) => frame.status)).toEqual(["completed"]);
  });

  it("fails a simulation whose source is too deep for a tsunami", async () => {
    const { simulation_id } = await submit({
      Mw: 8,
      h: 400,
      lat0: -15,
      lon0: -76,
      dia: "10",
      hhmm: "1230",
    });
    const seen = await frames(simulation_id);
    expect(seen.at(-1)?.status).toBe("failed");
  });

  it("streams one frame for a finished seeded simulation", async () => {
    const seen = await frames(COMPLETED);
    expect(seen.map((frame) => frame.status)).toEqual(["completed"]);
  });

  it("redirects an output to its canned file", async () => {
    const response = await call(`/api/v1/jobs/${COMPLETED}/outputs/max_height_map`);
    expect(response.status).toBe(307);
    const location = response.headers.get("location") ?? "";
    expect(location).toBe(`${FILES_PREFIX}max_height_map`);

    const file = stub.file(location);
    expect(file.headers.get("content-type")).toBe("application/pdf");
    expect((await file.text()).startsWith("%PDF-")).toBe(true);
  });

  it("answers 404 for an unknown job and an unknown output", async () => {
    expect((await call(`/api/v1/jobs/${crypto.randomUUID()}/events`)).status).toBe(404);
    expect((await call(`/api/v1/jobs/${COMPLETED}/outputs/nothing`)).status).toBe(404);
  });
});
