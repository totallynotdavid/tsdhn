import { and, desc, eq } from "drizzle-orm";

import { db } from "$lib/server/db";
import { type NewSimulation, type Simulation, simulation } from "$lib/server/db/schema";

export function createSimulation(data: NewSimulation): Promise<unknown> {
  return db.insert(simulation).values(data);
}

export function markDispatchAccepted(
  id: string,
  computeBackend: string,
  computeJobId: string,
): Promise<unknown> {
  return db
    .update(simulation)
    .set({
      status: "queued",
      computeBackend,
      computeJobId,
      error: null,
      artifactsAvailable: false,
      dispatchedAt: new Date(),
      finishedAt: null,
    })
    .where(eq(simulation.id, id));
}

export function markDispatchFailed(id: string, error: string): Promise<unknown> {
  return db
    .update(simulation)
    .set({
      status: "dispatch_failed",
      error,
      finishedAt: new Date(),
    })
    .where(eq(simulation.id, id));
}

export function listSimulations(userId: string): Promise<Simulation[]> {
  return db
    .select()
    .from(simulation)
    .where(eq(simulation.userId, userId))
    .orderBy(desc(simulation.createdAt));
}

export async function getSimulation(userId: string, id: string): Promise<Simulation | undefined> {
  const rows = await db
    .select()
    .from(simulation)
    .where(and(eq(simulation.id, id), eq(simulation.userId, userId)))
    .limit(1);
  return rows[0];
}

export function syncStatus(
  id: string,
  status: string,
  artifactsAvailable: boolean,
  snapshot?: {
    details?: string | null;
    step?: string | null;
    step_index?: number | null;
    total_steps?: number | null;
    calculation?: unknown;
    travel_times?: unknown;
    result_bucket?: string | null;
    result_key?: string | null;
    error?: string | null;
    finished_at?: string | null;
  },
): Promise<unknown> {
  const terminal = status === "completed" || status === "failed" || status === "cancelled";
  const finishedAt = terminal
    ? snapshot?.finished_at
      ? new Date(snapshot.finished_at)
      : new Date()
    : null;
  return db
    .update(simulation)
    .set({
      status,
      artifactsAvailable,
      details: snapshot?.details ?? null,
      step: snapshot?.step ?? null,
      stepIndex: snapshot?.step_index ?? null,
      totalSteps: snapshot?.total_steps ?? null,
      calculation: snapshot?.calculation ?? null,
      travelTimes: snapshot?.travel_times ?? null,
      resultBucket: snapshot?.result_bucket ?? null,
      resultKey: snapshot?.result_key ?? null,
      error: snapshot?.error ?? null,
      finishedAt,
    })
    .where(eq(simulation.id, id));
}
