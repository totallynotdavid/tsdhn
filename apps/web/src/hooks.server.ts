import type { Handle } from "@sveltejs/kit/hooks";
import { building } from "$app/env";
import { auth } from "#lib/server/auth.js";
import { db } from "#lib/server/db/index.js";
import { createSimulationRepository } from "#lib/server/simulation-repository.js";
import { svelteKitHandler } from "better-auth/svelte-kit";

const simulationRepository = createSimulationRepository(db);

const handleBetterAuth: Handle = async ({ event, resolve }) => {
  event.locals.simulationRepository = simulationRepository;

  const session = await auth.api.getSession({ headers: event.request.headers });

  if (session) {
    event.locals.session = session.session;
    event.locals.user = session.user;
  }

  return svelteKitHandler({ event, resolve, auth, building });
};

export const handle: Handle = handleBetterAuth;
