import { error } from "@sveltejs/kit";

import { backend } from "$lib/server/api";
import { getSimulation, syncStatus } from "$lib/server/simulations";

import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ params, locals, fetch }) => {
  const user = locals.user;
  if (!user) error(401);

  const sim = await getSimulation(user.id, params.id);
  if (!sim) error(404, "Simulación no encontrada");

  const client = backend(fetch);
  const { data: status } = await client.GET("/api/v1/simulations/{sim_id}", {
    params: { path: { sim_id: params.id } },
  });

  if (status) {
    await syncStatus(sim.id, status.status, status.report_available, status.error);
    sim.status = status.status;
    sim.reportAvailable = status.report_available;
  }

  return { sim, status: status ?? null };
};
