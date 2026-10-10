import { error, json } from "@sveltejs/kit";

import { earthquakeSchema, toEarthquakeInput } from "#lib/schema/earthquake.js";
import { computeClient } from "#lib/server/compute-api.js";

import type { RequestHandler } from "./$types";

export const POST: RequestHandler = async ({ request, locals, fetch }) => {
  if (!locals.user) error(401);

  const parsed = earthquakeSchema.safeParse(await request.json().catch(() => null));
  if (!parsed.success) error(400, parsed.error.issues[0]?.message ?? "Datos no válidos");

  const client = computeClient(fetch);
  const { data, error: apiError } = await client.POST("/api/v1/calculations", {
    body: toEarthquakeInput(parsed.data),
  });

  if (apiError || !data) error(502, "No se pudo calcular el estimado.");
  return json(data);
};
