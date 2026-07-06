import { error } from "@sveltejs/kit";

import { backend } from "$lib/server/api";
import { listSimulations, syncStatus } from "$lib/server/simulations";

import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ locals, fetch }) => {
  const user = locals.user;
  if (!user) error(401);

  const simulations = await listSimulations(user.id);
  const client = backend(fetch);

  await Promise.all(
    simulations
      .filter((s) => s.status === "queued" || s.status === "running")
      .map(async (s) => {
        const { data } = await client.GET("/api/v1/simulations/{sim_id}", {
          params: { path: { sim_id: s.id } },
        });
        if (data) {
          await syncStatus(s.id, data.status, data.report_available, data.error);
          s.status = data.status;
          s.reportAvailable = data.report_available;
        }
      }),
  );

  return { simulations };
};
