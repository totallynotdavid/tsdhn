import { BETTER_AUTH_SECRET, ORIGIN, TSDHN_PREVIEW } from "$app/env/private";
import { betterAuth } from "better-auth/minimal";
import { drizzleAdapter } from "@better-auth/drizzle-adapter";
import { sveltekitCookies } from "better-auth/svelte-kit";
import { getRequestEvent } from "$app/server";
import { db } from "#lib/server/db/index.js";

export const auth = betterAuth({
  // Preview requests may use any host name.
  baseURL:
    TSDHN_PREVIEW === "1" ? { allowedHosts: ["*"], protocol: "http", fallback: ORIGIN } : ORIGIN,
  secret: BETTER_AUTH_SECRET,
  database: drizzleAdapter(db, { provider: "pg" }),
  emailAndPassword: { enabled: true },
  plugins: [sveltekitCookies(getRequestEvent)],
});
