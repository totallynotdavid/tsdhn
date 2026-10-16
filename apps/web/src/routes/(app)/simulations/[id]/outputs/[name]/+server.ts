import { error } from "@sveltejs/kit";

import { computeRequestConfig } from "#lib/server/compute-api.js";
import { assertOutputAccessible } from "#lib/server/outputs.js";

import type { RequestHandler } from "./$types";

const RELAYED_HEADERS = ["content-type", "content-length", "content-disposition"];

/** Stream private object storage through the web app. */
export const GET: RequestHandler = async ({ params, locals, fetch }) => {
  if (!locals.user) error(401);

  const sim = await locals.simulationRepository.getSimulation(locals.user.id, params.id);
  assertOutputAccessible(sim, params.name);

  const { url, headers } = computeRequestConfig();
  const upstream = await fetch(
    `${url}/api/v1/jobs/${encodeURIComponent(sim.id)}/outputs/${encodeURIComponent(params.name)}`,
    { headers, redirect: "manual" },
  );

  if (upstream.status === 410) error(410, "Los archivos de esta simulación se eliminaron.");

  const location = upstream.headers.get("location");
  if (upstream.status !== 307 || !location) {
    error(502, "No se pudo preparar la descarga.");
  }

  const file = await fetch(location);
  if (!file.ok || !file.body) error(502, "No se pudo leer el resultado.");

  const relayed = new Headers();
  for (const name of RELAYED_HEADERS) {
    const value = file.headers.get(name);
    if (value) relayed.set(name, value);
  }
  return new Response(file.body, { headers: relayed });
};
