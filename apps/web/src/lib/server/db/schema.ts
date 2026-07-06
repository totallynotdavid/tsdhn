import { relations, sql } from "drizzle-orm";
import { index, integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

import { user } from "./auth.schema";

/**
 * A tsunami simulation submitted through the web app.
 *
 * `id` is the control-plane app_job_id. It is generated before dispatch and is
 * the stable public id used in URLs and user history.
 */
export const simulation = sqliteTable(
  "simulation",
  {
    id: text("id").primaryKey(),
    userId: text("user_id")
      .notNull()
      .references(() => user.id, { onDelete: "cascade" }),
    params: text("params", { mode: "json" }).notNull(),
    skipSteps: text("skip_steps", { mode: "json" })
      .notNull()
      .default(sql`'[]'`),
    status: text("status").notNull().default("pending_dispatch"),
    computeBackend: text("compute_backend"),
    computeJobId: text("compute_job_id"),
    resultBucket: text("result_bucket"),
    resultKey: text("result_key"),
    details: text("details"),
    step: text("step"),
    stepIndex: integer("step_index"),
    totalSteps: integer("total_steps"),
    calculation: text("calculation", { mode: "json" }),
    travelTimes: text("travel_times", { mode: "json" }),
    reportAvailable: integer("report_available", { mode: "boolean" }).notNull().default(false),
    error: text("error"),
    createdAt: integer("created_at", { mode: "timestamp_ms" })
      .default(sql`(cast(unixepoch('subsecond') * 1000 as integer))`)
      .notNull(),
    updatedAt: integer("updated_at", { mode: "timestamp_ms" })
      .default(sql`(cast(unixepoch('subsecond') * 1000 as integer))`)
      .$onUpdate(() => /* @__PURE__ */ new Date())
      .notNull(),
    dispatchedAt: integer("dispatched_at", { mode: "timestamp_ms" }),
    finishedAt: integer("finished_at", { mode: "timestamp_ms" }),
  },
  (table) => [
    index("simulation_userId_idx").on(table.userId),
    index("simulation_user_createdAt_idx").on(table.userId, table.createdAt),
    index("simulation_status_idx").on(table.status),
    index("simulation_compute_idx").on(table.computeBackend, table.computeJobId),
  ],
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
