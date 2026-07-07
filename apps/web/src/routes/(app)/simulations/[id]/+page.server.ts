import { error, fail, redirect } from "@sveltejs/kit";

import { backend } from "$lib/server/api";
import { dispatchSimulation } from "$lib/server/dispatch";
import { getSimulation, syncStatus } from "$lib/server/simulations";

import type { Actions, PageServerLoad } from "./$types";

const TERMINAL = new Set(["completed", "failed", "dispatch_failed", "cancelled"]);
const RETRYABLE = new Set(["pending_dispatch", "dispatch_failed"]);

export const load: PageServerLoad = async ({ params, locals, fetch }) => {
  const user = locals.user;
  if (!user) error(401);

  const sim = await getSimulation(user.id, params.id);
  if (!sim) error(404, "Simulación no encontrada");

  if (TERMINAL.has(sim.status)) return { sim, status: null };
  if (!sim.computeJobId) return { sim, status: null };

  const client = backend(fetch);
  const { data: status } = await client.GET("/api/v1/jobs/{app_job_id}", {
    params: { path: { app_job_id: sim.id } },
  });
  if (status) {
    await syncStatus(sim.id, status.status, status.artifacts_available, status);
    sim.status = status.status;
    sim.artifactsAvailable = status.artifacts_available;
    sim.details = status.details ?? null;
    sim.step = status.step ?? null;
    sim.stepIndex = status.step_index ?? null;
    sim.totalSteps = status.total_steps ?? null;
    sim.calculation = status.calculation ?? null;
    sim.travelTimes = status.travel_times ?? null;
    sim.error = status.error ?? null;
  }

  return { sim, status: status ?? null };
};

export const actions: Actions = {
  retry: async ({ params, locals, fetch }) => {
    const user = locals.user;
    if (!user) error(401);

    const sim = await getSimulation(user.id, params.id);
    if (!sim) error(404, "Simulación no encontrada");

    if (!RETRYABLE.has(sim.status)) {
      return fail(400, { retryError: "Esta simulación ya no se puede reenviar." });
    }

    const client = backend(fetch);
    const dispatch = await dispatchSimulation(sim, client, sim.computeBackend ?? undefined);
    if (!dispatch.ok) return fail(502, { retryError: dispatch.error });

    redirect(303, `/simulations/${sim.id}`);
  },
};
