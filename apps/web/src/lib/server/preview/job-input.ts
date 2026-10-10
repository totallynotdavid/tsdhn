import { jsonb, pgSchema, uuid } from "drizzle-orm/pg-core";

import type { EarthquakeInput } from "#lib/schema/earthquake.js";

/** The input each compute job was created with, which a repeated submission is compared with. */
export const jobInput = pgSchema("compute").table("job_inputs", {
  simulationId: uuid("simulation_id").primaryKey(),
  input: jsonb("input").$type<EarthquakeInput>().notNull(),
});
