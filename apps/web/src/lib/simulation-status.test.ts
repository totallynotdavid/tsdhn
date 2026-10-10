import { describe, expect, it } from "vitest";

import { canResubmit, isFinished, isInFlight, progressOf, statusMeta } from "./simulation-status";

const job = { status: "running", step: null, stepIndex: null, totalSteps: null };

describe("simulation status", () => {
  it("separates states that can be resent, watched and settled", () => {
    expect(canResubmit("submission_failed")).toBe(true);
    expect(canResubmit("failed")).toBe(false);
    expect(isInFlight("running")).toBe(true);
    expect(isInFlight("submitting")).toBe(false);
    expect(isFinished("completed")).toBe(true);
    expect(isFinished("queued")).toBe(false);
  });

  it("keeps an unknown status readable", () => {
    expect(statusMeta("paused")).toEqual({ label: "paused", tone: "neutral" });
  });
});

describe("progress", () => {
  it("names the step instead of the pipeline identifier", () => {
    const progress = progressOf({ ...job, step: "tsunami", stepIndex: 3, totalSteps: 8 });

    expect(progress.label).toBe("Propagación del tsunami");
    expect(progress.position).toBe("3 de 8");
    expect(progress.percent).toBe(31);
  });

  it("shows movement during the first step", () => {
    const progress = progressOf({ ...job, step: "fault_plane", stepIndex: 1, totalSteps: 8 });

    expect(progress.percent).toBeGreaterThan(0);
  });

  it("explains waiting without a percentage", () => {
    expect(progressOf({ ...job, status: "queued" })).toMatchObject({ percent: null });
    expect(progressOf(job).label).toBe("Preparando el cálculo");
  });
});
