import { DATABASE_URL, TSDHN_PREVIEW } from "$app/env/private";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";

import type { SimulationDatabase } from "#lib/server/simulation-repository.js";

import * as schema from "./schema";

async function connect(): Promise<SimulationDatabase> {
  if (TSDHN_PREVIEW === "1") {
    const { createPreviewDatabase } = await import("#lib/server/preview/database.js");
    return createPreviewDatabase({ NODE_ENV: process.env.NODE_ENV, DATABASE_URL });
  }
  if (!DATABASE_URL?.trim()) throw new Error("DATABASE_URL is not set");
  return drizzle(postgres(DATABASE_URL, { max: 10 }), { schema });
}

export const db = await connect();
