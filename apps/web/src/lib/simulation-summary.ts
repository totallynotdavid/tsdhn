import type { components } from "@tsdhn/api-client";

import type { EarthquakeInput } from "#lib/schema/earthquake.js";
import { type Progress, progressOf } from "#lib/simulation-status.js";
import type { SimulationDetails } from "#lib/server/simulation-details.js";

type Calculation = components["schemas"]["CalculationResponse"];

/** What a row of the simulation list needs, so the list never ships travel-time tables. */
export interface SimulationSummary {
  id: string;
  createdAt: Date;
  status: string;
  magnitude: number;
  latitude: number;
  longitude: number;
  /** The engine's one-line verdict, once the source is calculated. */
  warning: string | null;
  progress: Progress | null;
}

export function summarize(sim: SimulationDetails): SimulationSummary {
  const params = sim.params as EarthquakeInput;
  const calculation = sim.calculation as Calculation | null;
  return {
    id: sim.id,
    createdAt: sim.createdAt,
    status: sim.status,
    magnitude: params.Mw,
    latitude: params.lat0,
    longitude: params.lon0,
    warning: calculation?.tsunami_warning ?? null,
    progress: sim.status === "running" || sim.status === "queued" ? progressOf(sim) : null,
  };
}
