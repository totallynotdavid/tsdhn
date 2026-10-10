import { fail, redirect } from "@sveltejs/kit";
import { message, superValidate } from "sveltekit-superforms";
import { zod4 } from "sveltekit-superforms/adapters";

import {
  defaultEarthquake,
  type EarthquakeInput,
  earthquakeFromInput,
  earthquakeSchema,
  toEarthquakeInput,
} from "#lib/schema/earthquake.js";
import { computeClient } from "#lib/server/compute-api.js";
import { submitSimulation } from "#lib/server/submit-simulation.js";

import type { Actions, PageServerLoad } from "./$types";

export const load: PageServerLoad = async ({ locals, url }) => {
  const from = url.searchParams.get("from");
  const past =
    from && locals.user
      ? await locals.simulationRepository.getSimulation(locals.user.id, from)
      : undefined;
  const values = past
    ? earthquakeFromInput(past.params as EarthquakeInput, past.createdAt)
    : defaultEarthquake();

  return { form: await superValidate(values, zod4(earthquakeSchema)) };
};

export const actions: Actions = {
  default: async ({ request, locals, fetch }) => {
    const user = locals.user;
    if (!user) redirect(303, "/login");

    const form = await superValidate(request, zod4(earthquakeSchema));
    if (!form.valid) return fail(400, { form });

    const input = toEarthquakeInput(form.data);
    const simulationId = crypto.randomUUID();

    await locals.simulationRepository.createSimulation({
      id: simulationId,
      userId: user.id,
      params: input,
    });

    const client = computeClient(fetch);
    const submission = await submitSimulation(
      { id: simulationId, params: input },
      client,
      locals.simulationRepository,
    );
    if (!submission.ok) {
      return message(form, "No se pudo iniciar la simulación. Intente de nuevo en un momento.", {
        status: 502,
      });
    }

    redirect(303, `/simulations/${simulationId}`);
  },
};
