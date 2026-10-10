import type { Handle } from "@sveltejs/kit/hooks";

import type { auth as Auth } from "#lib/server/auth.js";
import type { SimulationDatabase } from "#lib/server/simulation-repository.js";

import { COMPUTE_STUB_PREFIX, createComputeStub, FILES_PREFIX } from "./compute-stub.js";
import { DEMO_USER } from "./canned.js";

/** These pages remain signed out. All other pages sign in the demo user first. */
const SIGNED_OUT_PAGES = new Set(["/login", "/signup"]);

interface Options {
  auth: typeof Auth;
  db: SimulationDatabase;
  computeApiToken: string;
}

/** Serve the compute stub and sign in the demo user for other pages. */
export function createPreviewHandle({ auth, db, computeApiToken }: Options): Handle {
  const stub = createComputeStub({ db, token: computeApiToken });

  return async ({ event, resolve }) => {
    const { pathname } = event.url;
    if (pathname.startsWith(COMPUTE_STUB_PREFIX)) return stub.handle(event.request);
    if (pathname.startsWith(FILES_PREFIX)) return stub.file(pathname);

    if (SIGNED_OUT_PAGES.has(pathname) || pathname.startsWith("/api/auth")) return resolve(event);
    if (await auth.api.getSession({ headers: event.request.headers })) return resolve(event);

    await auth.api.signInEmail({
      body: { email: DEMO_USER.email, password: DEMO_USER.password },
      headers: event.request.headers,
    });
    const cookie = event.cookies
      .getAll()
      .map(({ name, value }) => `${name}=${encodeURIComponent(value)}`)
      .join("; ");
    event.request.headers.set("cookie", cookie);
    return resolve(event);
  };
}
