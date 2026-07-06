import { relations, sql } from "drizzle-orm";
import { index, integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

import { user } from "./auth.schema";

/**
 * A tsunami simulation submitted through the web app.
 *
 * `id` is the backend job id. The web DB owns user attribution, submitted
 * parameters, and terminal outcome. Redis owns live progress.
 */
export const simulation = sqliteTable(
  "simulation",
  {
    id: text("id").primaryKey(),
    userId: text("user_id")
      .notNull()
      .references(() => user.id, { onDelete: "cascade" }),
    params: text("params", { mode: "json" }).notNull(),
    status: text("status").notNull().default("queued"),
    reportAvailable: integer("report_available", { mode: "boolean" }).notNull().default(false),
    error: text("error"),
    createdAt: integer("created_at", { mode: "timestamp_ms" })
      .default(sql`(cast(unixepoch('subsecond') * 1000 as integer))`)
      .notNull(),
    updatedAt: integer("updated_at", { mode: "timestamp_ms" })
      .default(sql`(cast(unixepoch('subsecond') * 1000 as integer))`)
      .$onUpdate(() => /* @__PURE__ */ new Date())
      .notNull(),
    finishedAt: integer("finished_at", { mode: "timestamp_ms" }),
  },
  (table) => [index("simulation_userId_idx").on(table.userId)],
);

export const simulationRelations = relations(simulation, ({ one }) => ({
  user: one(user, {
    fields: [simulation.userId],
    references: [user.id],
  }),
}));

export type Simulation = typeof simulation.$inferSelect;
export type NewSimulation = typeof simulation.$inferInsert;

export * from "./auth.schema";
