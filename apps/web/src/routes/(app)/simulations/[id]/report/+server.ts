import { error } from "@sveltejs/kit";

import { backendRaw } from "$lib/server/api";
import { getSimulation } from "$lib/server/simulations";

import type { RequestHandler } from "./$types";

export const GET: RequestHandler = async ({ params, locals, fetch }) => {
  if (!locals.user) error(401);
  const sim = await getSimulation(locals.user.id, params.id);
  if (!sim) error(404);
  if (!sim.computeJobId) error(409, "La simulación aún no fue aceptada por el backend.");

  const { url, headers } = backendRaw();
  const upstream = await fetch(`${url}/api/v1/jobs/${encodeURIComponent(sim.id)}/report`, {
    headers,
  });
  if (!upstream.ok || !upstream.body) {
    error(upstream.status === 425 ? 425 : 404, "El reporte aún no está disponible.");
  }

  return new Response(upstream.body, {
    headers: {
      "content-type": "application/pdf",
      "content-disposition": `attachment; filename="tsdhn_${sim.id}.pdf"`,
    },
  });
};
