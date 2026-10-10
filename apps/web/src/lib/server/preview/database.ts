import { PGlite } from "@electric-sql/pglite";
import { hashPassword } from "better-auth/crypto";
import { drizzle } from "drizzle-orm/pglite";
import { migrate } from "drizzle-orm/pglite/migrator";

import type { EarthquakeInput } from "#lib/schema/earthquake.js";
import { computeJob } from "#lib/server/db/compute.js";
import * as schema from "#lib/server/db/schema.js";
import type { NewSimulation } from "#lib/server/db/schema.js";
import type { SimulationDatabase } from "#lib/server/simulation-repository.js";

import { calculationFor, DEMO_USER, STEPS, storedOutputs, travelTimesFor } from "./canned.js";
import { jobInput } from "./job-input.js";

const MIGRATIONS = new URL("../../../../drizzle", import.meta.url).pathname;

// The compute service owns this table in a real stack; the web app only reads it.
const COMPUTE_JOBS = `
  CREATE SCHEMA compute;
  CREATE TABLE compute.jobs (
    id uuid PRIMARY KEY,
    simulation_id uuid UNIQUE NOT NULL,
    status text NOT NULL,
    details text,
    step text,
    step_index integer,
    total_steps integer,
    calculation jsonb,
    travel_times jsonb,
    outputs jsonb NOT NULL DEFAULT '[]'::jsonb,
    error text,
    started_at timestamptz,
    finished_at timestamptz
  );
  CREATE TABLE compute.job_inputs (
    simulation_id uuid PRIMARY KEY,
    input jsonb NOT NULL
  );
`;

const MINUTE = 60_000;

type NewComputeJob = typeof computeJob.$inferInsert;

interface Seeded {
  id: string;
  /** Minutes before now that the user submitted it. */
  ago: number;
  input: Omit<EarthquakeInput, "dia" | "hhmm">;
  job:
    | { status: "completed"; minutes: number }
    | { status: "running"; stepIndex: number }
    | { status: "queued" }
    | { status: "failed"; error: string }
    | { status: "submission_failed"; error: string };
}

export const SEEDED: Seeded[] = [
  {
    id: "00000000-0000-4000-8000-000000000001",
    ago: 180,
    input: { Mw: 8.4, h: 15, lat0: -19.6, lon0: -71.2 },
    job: { status: "completed", minutes: 62 },
  },
  {
    id: "00000000-0000-4000-8000-000000000002",
    ago: 25,
    input: { Mw: 8.1, h: 20, lat0: -12.5, lon0: -78.4 },
    job: { status: "running", stepIndex: 3 },
  },
  {
    id: "00000000-0000-4000-8000-000000000003",
    ago: 2,
    input: { Mw: 7.6, h: 30, lat0: -15.8, lon0: -75.9 },
    job: { status: "queued" },
  },
  {
    id: "00000000-0000-4000-8000-000000000004",
    ago: 1500,
    input: { Mw: 8, h: 25, lat0: -33.2, lon0: -72.4 },
    job: {
      status: "failed",
      error:
        'Traceback (most recent call last):\n  File "tsdhn/engine.py", line 131, in run\n    step.run(context)\nRuntimeError: tsunami step exited with status 1 (preview failure)',
    },
  },
  {
    id: "00000000-0000-4000-8000-000000000005",
    ago: 10,
    input: { Mw: 7.4, h: 35, lat0: -5.9, lon0: -81.5 },
    job: {
      status: "submission_failed",
      error: "connect ECONNREFUSED 127.0.0.1:8000 (preview failure)",
    },
  },
  {
    id: "00000000-0000-4000-8000-000000000006",
    ago: 4300,
    input: { Mw: 7.8, h: 10, lat0: -10.1, lon0: -79.6 },
    job: { status: "completed", minutes: 48 },
  },
];

/** The event time the engine takes as input: UTC day and "HHMM". */
function eventFields(when: Date): Pick<EarthquakeInput, "dia" | "hhmm"> {
  return {
    dia: String(when.getUTCDate()).padStart(2, "0"),
    hhmm:
      String(when.getUTCHours()).padStart(2, "0") + String(when.getUTCMinutes()).padStart(2, "0"),
  };
}

function seededRows({ id, ago, input: partial, job }: Seeded, now: number) {
  const createdAt = new Date(now - ago * MINUTE);
  const input: EarthquakeInput = {
    ...partial,
    ...eventFields(new Date(now - (ago + 5) * MINUTE)),
  };
  const simulation: NewSimulation = {
    id,
    userId: DEMO_USER.id,
    params: input,
    createdAt,
    submissionError: job.status === "submission_failed" ? job.error : null,
  };
  if (job.status === "submission_failed") return { simulation, job: null, input: null };

  const started = new Date(createdAt.getTime() + MINUTE);
  const base = { id: crypto.randomUUID(), simulationId: id };
  const computed = {
    totalSteps: STEPS.length,
    calculation: calculationFor(input),
    travelTimes: travelTimesFor(input),
    startedAt: started,
  };
  let row: NewComputeJob;
  switch (job.status) {
    case "queued":
      row = { ...base, status: "queued" };
      break;
    case "running":
      row = {
        ...base,
        ...computed,
        status: "running",
        step: STEPS[job.stepIndex - 1],
        stepIndex: job.stepIndex,
      };
      break;
    case "failed":
      row = {
        ...base,
        ...computed,
        status: "failed",
        step: STEPS[2],
        stepIndex: 3,
        error: job.error,
        finishedAt: new Date(createdAt.getTime() + 20 * MINUTE),
      };
      break;
    case "completed":
      row = {
        ...base,
        ...computed,
        status: "completed",
        step: STEPS[STEPS.length - 1],
        stepIndex: STEPS.length,
        outputs: storedOutputs(),
        finishedAt: new Date(createdAt.getTime() + job.minutes * MINUTE),
      };
      break;
  }
  return { simulation, job: row, input: { simulationId: id, input } };
}

async function seed(db: SimulationDatabase): Promise<void> {
  const now = Date.now();
  await db.insert(schema.user).values({
    id: DEMO_USER.id,
    name: DEMO_USER.name,
    email: DEMO_USER.email,
    emailVerified: true,
  });
  await db.insert(schema.account).values({
    id: `${DEMO_USER.id}-credential`,
    accountId: DEMO_USER.id,
    providerId: "credential",
    userId: DEMO_USER.id,
    password: await hashPassword(DEMO_USER.password),
  });

  const rows = SEEDED.map((seeded) => seededRows(seeded, now));
  await db.insert(schema.simulation).values(rows.map((row) => row.simulation));
  await db.insert(computeJob).values(rows.flatMap((row) => (row.job ? [row.job] : [])));
  await db.insert(jobInput).values(rows.flatMap((row) => (row.input ? [row.input] : [])));
}

export async function createPreviewDatabase(): Promise<SimulationDatabase> {
  const client = new PGlite();
  const db = drizzle(client, { schema });
  await migrate(db, { migrationsFolder: MIGRATIONS });
  await client.exec(COMPUTE_JOBS);
  await seed(db);
  return db;
}
