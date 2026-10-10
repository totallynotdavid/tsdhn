import { building } from "$app/env";
import { defineEnvVars } from "@sveltejs/kit/env";
import { z } from "zod";

/** Preview mode supplies defaults for service variables. */
const previewing = process.env.TSDHN_PREVIEW === "1";

const schema = (fallback: string) =>
  building || previewing ? z.string().default(fallback) : z.string();

export const variables = defineEnvVars({
  ORIGIN: { schema: schema("http://localhost:3000") },
  BETTER_AUTH_SECRET: { schema: schema("tsdhn-build-secret") },
  // The preview launcher passes no database URL.
  DATABASE_URL: {
    schema: previewing ? z.string().optional() : schema("postgres://localhost/test"),
  },
  COMPUTE_API_URL: { schema: schema("http://localhost:8000") },
  COMPUTE_API_TOKEN: { schema: schema("tsdhn-build-token") },
  TSDHN_PREVIEW: { schema: z.string().optional() },
});
