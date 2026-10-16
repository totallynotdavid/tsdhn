import { json } from "@sveltejs/kit";
import { sql } from "drizzle-orm";

import { db } from "#lib/server/db/index.js";

import type { RequestHandler } from "./$types";

export const GET: RequestHandler = async () => {
  try {
    await db.execute(sql`select 1`);
  } catch {
    return json({ status: "degraded", database_connected: false }, { status: 503 });
  }
  return json({ status: "healthy", database_connected: true });
};
