import { error, redirect } from "@sveltejs/kit";

import { summarize } from "#lib/simulation-summary.js";

import type { PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ locals }) => {
  const user = locals.user;
  if (!user) error(401);

  const simulations = await locals.simulationRepository.listSimulations(user.id);
  if (simulations.length === 0) redirect(303, "/new");

  return { simulations: simulations.map(summarize) };
};
