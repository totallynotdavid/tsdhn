import { and, desc, eq } from "drizzle-orm";

import { db } from "$lib/server/db";
import { type NewSimulation, type Simulation, simulation } from "$lib/server/db/schema";

export function createSimulation(data: NewSimulation): Promise<unknown> {
  return db.insert(simulation).values(data);
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
  reportAvailable: boolean,
  error?: string | null,
): Promise<unknown> {
  const terminal = status === "completed" || status === "failed";
  return db
    .update(simulation)
    .set({
      status,
      reportAvailable,
      error: error ?? null,
      finishedAt: terminal ? new Date() : null,
    })
    .where(eq(simulation.id, id));
}
