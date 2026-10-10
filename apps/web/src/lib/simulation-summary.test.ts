import { describe, expect, it } from "vitest";

import type { SimulationDetails } from "#lib/server/simulation-details.js";

import { summarize } from "./simulation-summary";

function sim(overrides: Partial<SimulationDetails>): SimulationDetails {
  return {
    id: "sim-1",
    userId: "user-1",
    params: { Mw: 8.4, h: 25, lat0: -17.6, lon0: -71.9, dia: "09", hhmm: "2105" },
    createdAt: new Date("2026-10-09T21:05:00Z"),
    submissionError: null,
    status: "completed",
    details: null,
    step: null,
    stepIndex: null,
    totalSteps: null,
    calculation: null,
    travelTimes: { arrival_times: { Arica: "00:19 10Oct" }, distances: {}, epicenter_info: {} },
    error: null,
    outputs: [],
    startedAt: null,
    finishedAt: null,
    ...overrides,
  };
}

describe("simulation summary", () => {
  it("keeps the verdict and drops the travel-time tables", () => {
    const summary = summarize(
      sim({ calculation: { tsunami_warning: "Genera un Tsunami pequeno" } }),
    );

    expect(summary).toEqual({
      id: "sim-1",
      createdAt: new Date("2026-10-09T21:05:00Z"),
      status: "completed",
      magnitude: 8.4,
      latitude: -17.6,
      longitude: -71.9,
      warning: "Genera un Tsunami pequeno",
      progress: null,
    });
  });

  it("reports progress only while the simulation moves", () => {
    const running = summarize(
      sim({ status: "running", step: "deform", stepIndex: 2, totalSteps: 8 }),
    );

    expect(running.progress).toMatchObject({
      label: "Deformación del fondo marino",
      position: "2 de 8",
    });
    expect(summarize(sim({ status: "failed" })).progress).toBeNull();
  });
});
