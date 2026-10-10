import { isDeepStrictEqual } from "node:util";

import { and, eq, inArray } from "drizzle-orm";

import type { EarthquakeInput } from "#lib/schema/earthquake.js";
import { computeJob, type ComputeJob } from "#lib/server/db/compute.js";
import type { SimulationDatabase } from "#lib/server/simulation-repository.js";

import { calculationFor, OUTPUTS, STEPS, storedOutputs, travelTimesFor } from "./canned.js";
import { jobInput } from "./job-input.js";

export const COMPUTE_STUB_PREFIX = "/_preview/compute";
export const FILES_PREFIX = "/_preview/files/";

/** Source depth beyond which a submitted simulation fails, as a deep quake makes no tsunami. */
const DEEPEST_SOURCE_KM = 300;
/** A deep submission fails during this step. */
const FAILING_STEP = 3;

interface Options {
  db: SimulationDatabase;
  token: string;
  /** Pause between the stages of a submitted simulation. */
  stepMs?: number;
}

const json = (body: unknown, status = 200) => Response.json(body, { status });

function isInput(value: unknown): value is EarthquakeInput {
  if (typeof value !== "object" || value === null) return false;
  const input = value as Record<string, unknown>;
  return ["Mw", "h", "lat0", "lon0"].every((key) => typeof input[key] === "number");
}

function frameOf(job: ComputeJob) {
  return {
    status: job.status,
    details: job.details,
    step: job.step,
    step_index: job.stepIndex,
    total_steps: job.totalSteps,
    calculation: job.calculation,
    travel_times: job.travelTimes,
    error: job.error,
    outputs: (job.outputs ?? []).map((output) => output.name),
  };
}

const UNFINISHED = ["queued", "running"];
const FINISHED = new Set(["completed", "failed"]);

/** Implements the compute API against the preview database. */
export function createComputeStub({ db, token, stepMs = 2500 }: Options) {
  async function jobOf(simulationId: string): Promise<ComputeJob | undefined> {
    const rows = await db
      .select()
      .from(computeJob)
      .where(eq(computeJob.simulationId, simulationId));
    return rows[0];
  }

  /** Write a stage only while the job is unfinished, so a finished job never changes again. */
  async function update(simulationId: string, values: Partial<ComputeJob>): Promise<void> {
    await db
      .update(computeJob)
      .set(values)
      .where(
        and(eq(computeJob.simulationId, simulationId), inArray(computeJob.status, UNFINISHED)),
      );
  }

  function run(simulationId: string, input: EarthquakeInput): void {
    const calculation = calculationFor(input);
    const travelTimes = travelTimesFor(input);
    const tooDeep = input.h > DEEPEST_SOURCE_KM;
    const steps = tooDeep ? STEPS.slice(0, FAILING_STEP) : STEPS;

    const stages: (() => Partial<ComputeJob>)[] = [
      () => ({ status: "running", startedAt: new Date() }),
      ...steps.map((step, index) => () => ({
        step,
        stepIndex: index + 1,
        totalSteps: STEPS.length,
        calculation,
        travelTimes,
      })),
      tooDeep
        ? () => ({
            status: "failed",
            error: `RuntimeError: the source at ${input.h} km is deeper than ${DEEPEST_SOURCE_KM} km and makes no tsunami (preview failure)`,
            finishedAt: new Date(),
          })
        : () => ({ status: "completed", outputs: storedOutputs(), finishedAt: new Date() }),
    ];
    stages.forEach((stage, index) => {
      const timer = setTimeout(() => void update(simulationId, stage()), (index + 1) * stepMs);
      timer.unref();
    });
  }

  async function submit(request: Request): Promise<Response> {
    const body = (await request.json().catch(() => null)) as {
      simulation_id?: unknown;
      input?: unknown;
    } | null;
    if (typeof body?.simulation_id !== "string" || !isInput(body.input)) {
      return json({ detail: "simulation_id and input are required" }, 422);
    }
    const { simulation_id: simulationId, input } = body as {
      simulation_id: string;
      input: EarthquakeInput;
    };
    const created = await db.transaction(async (tx) => {
      const inserted = await tx
        .insert(computeJob)
        .values({ id: crypto.randomUUID(), simulationId, status: "queued" })
        .onConflictDoNothing()
        .returning({ id: computeJob.id });
      if (inserted.length > 0) await tx.insert(jobInput).values({ simulationId, input });
      return inserted.length > 0;
    });
    if (created) {
      run(simulationId, input);
      return json({ simulation_id: simulationId, status: "queued" }, 201);
    }

    const [stored] = await db
      .select()
      .from(jobInput)
      .where(eq(jobInput.simulationId, simulationId));
    if (!stored || !isDeepStrictEqual(stored.input, input)) {
      return json({ detail: "Job id already exists with different input" }, 400);
    }
    return json({ simulation_id: simulationId, status: (await jobOf(simulationId))?.status });
  }

  async function calculate(request: Request): Promise<Response> {
    const input = await request.json().catch(() => null);
    if (!isInput(input)) return json({ detail: "Mw, h, lat0 and lon0 are required" }, 422);
    return json({ calculation: calculationFor(input), travel_times: travelTimesFor(input) });
  }

  /** Stream frames until the job finishes. */
  function events(simulationId: string): Response {
    const encoder = new TextEncoder();
    let timer: ReturnType<typeof setInterval> | undefined;
    let closed = false;
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        let last = "";
        let ticks = 0;
        const poll = async () => {
          const job = await jobOf(simulationId);
          if (closed || !job) return;
          const data = JSON.stringify(frameOf(job));
          if (data !== last) {
            last = data;
            controller.enqueue(encoder.encode(`data: ${data}\n\n`));
          } else if (++ticks % 15 === 0) {
            controller.enqueue(encoder.encode(": keepalive\n\n"));
          }
          if (FINISHED.has(job.status)) {
            closed = true;
            clearInterval(timer);
            controller.close();
          }
        };
        timer = setInterval(() => void poll(), 1000);
        void poll();
      },
      cancel() {
        closed = true;
        clearInterval(timer);
      },
    });
    return new Response(stream, { headers: { "content-type": "text/event-stream" } });
  }

  async function handle(request: Request): Promise<Response> {
    if (request.headers.get("authorization") !== `Bearer ${token}`) {
      return json({ detail: "Invalid or missing token" }, 401);
    }
    const path = new URL(request.url).pathname.slice(COMPUTE_STUB_PREFIX.length);

    if (path === "/api/v1/calculations" && request.method === "POST") return calculate(request);
    if (path === "/api/v1/jobs" && request.method === "POST") return submit(request);

    const job = /^\/api\/v1\/jobs\/([^/]+)\/(events|outputs\/([^/]+))$/.exec(path);
    if (job && request.method === "GET") {
      const [, simulationId, , name] = job;
      if (!(await jobOf(simulationId))) return json({ detail: "Job not found" }, 404);
      if (name === undefined) return events(simulationId);
      if (!(name in OUTPUTS)) return json({ detail: "Output not found" }, 404);
      return new Response(null, { status: 307, headers: { location: `${FILES_PREFIX}${name}` } });
    }
    return json({ detail: "Not found" }, 404);
  }

  function file(pathname: string): Response {
    const output = OUTPUTS[pathname.slice(FILES_PREFIX.length)];
    if (!output) return json({ detail: "Not found" }, 404);
    return new Response(output.body, {
      headers: {
        "content-type": output.content_type,
        "content-disposition": `attachment; filename="${output.filename}"`,
      },
    });
  }

  return { handle, file };
}
