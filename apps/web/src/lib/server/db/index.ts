import { DATABASE_URL } from "$app/env/private";
import { drizzle } from "drizzle-orm/postgres-js";
import postgres from "postgres";

import * as schema from "./schema";

if (!DATABASE_URL?.trim()) throw new Error("DATABASE_URL is not set");

const client = postgres(DATABASE_URL, { max: 10 });

export const db = drizzle(client, { schema });
