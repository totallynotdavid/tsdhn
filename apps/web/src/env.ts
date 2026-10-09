import { building } from "$app/env";
import { defineEnvVars } from "@sveltejs/kit/env";
import { z } from "zod";

const schema = (fallback: string) => (building ? z.string().default(fallback) : z.string());

export const variables = defineEnvVars({
  ORIGIN: { schema: schema("http://localhost:3000") },
  BETTER_AUTH_SECRET: { schema: schema("tsdhn-build-secret") },
  DATABASE_URL: { schema: schema("postgres://localhost/test") },
  COMPUTE_API_URL: { schema: schema("http://localhost:8000") },
  COMPUTE_API_TOKEN: { schema: schema("tsdhn-build-token") },
});
