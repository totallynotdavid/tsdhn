import { fail, redirect } from "@sveltejs/kit";
import { message, superValidate } from "sveltekit-superforms";
import { zod4 } from "sveltekit-superforms/adapters";

import { defaultEarthquake, earthquakeSchema, toEarthquakeInput } from "$lib/schema/earthquake";
import { backend } from "$lib/server/api";
import { createSimulation } from "$lib/server/simulations";

import type { Actions, PageServerLoad } from "./$types";

export const load: PageServerLoad = async () => {
  return { form: await superValidate(defaultEarthquake, zod4(earthquakeSchema)) };
};

export const actions: Actions = {
  default: async ({ request, locals, fetch }) => {
    const user = locals.user;
    if (!user) redirect(303, "/login");

    const form = await superValidate(request, zod4(earthquakeSchema));
    if (!form.valid) return fail(400, { form });

    const input = toEarthquakeInput(form.data);
    const client = backend(fetch);
    const { data, error: apiError } = await client.POST("/api/v1/simulations", {
      body: { input, skip_steps: [] },
    });

    if (apiError || !data) {
      return message(form, "No se pudo iniciar la simulación.", { status: 502 });
    }

    await createSimulation({
      id: data.id,
      userId: user.id,
      params: input,
      status: "queued",
    });

    redirect(303, `/simulations/${data.id}`);
  },
};
