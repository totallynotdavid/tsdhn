import { error, json } from "@sveltejs/kit";

import { backend } from "$lib/server/api";

import type { RequestHandler } from "./$types";

export const POST: RequestHandler = async ({ request, locals, fetch }) => {
  if (!locals.user) error(401);

  const body = await request.json();
  const client = backend(fetch);
  const { data, error: apiError } = await client.POST("/api/v1/calculations", { body });

  if (apiError || !data) error(502, "No se pudo calcular la vista previa.");
  return json(data);
};
