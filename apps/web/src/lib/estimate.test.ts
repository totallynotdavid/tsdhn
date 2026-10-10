import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { type Estimate, isStale, requestEstimate, type Result, shownResult } from "./estimate";
import type { EarthquakeForm } from "./schema/earthquake";

const values: EarthquakeForm = {
  magnitude: 8,
  depth: 10,
  latitude: -20.5,
  longitude: -70.5,
  datetime: "2026-10-09T23:30",
};

const preview = (port: string) =>
  ({
    calculation: { rectangle_corners: [] },
    travel_times: { arrival_times: { [port]: "00:28 10Oct" }, distances: {}, epicenter_info: {} },
  }) as never;

const answer = (port: string) => Promise.resolve(Response.json(preview(port)));

function collect() {
  const states: Estimate[] = [];
  return { states, report: (e: Estimate) => states.push(e) };
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("estimate request", () => {
  it("marks the previous result stale at once and pairs the answer with the event it was asked for", async () => {
    const { states, report } = collect();
    const send = vi.fn(() => answer("Ilo"));
    const previous: Result = {
      preview: preview("Callao"),
      input: { Mw: 7, h: 10, lat0: -12, lon0: -77, dia: "09", hhmm: "1200" },
    };

    requestEstimate(values, previous, report, { fetch: send as never });

    expect(states).toEqual([{ state: "loading", last: previous }]);
    expect(isStale(states[0])).toBe(true);
    expect(shownResult(states[0])).toBe(previous);
    expect(send).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(400);

    expect(send).toHaveBeenCalledOnce();
    const done = states[1];
    expect(done.state).toBe("ready");
    expect(shownResult(done)?.input).toMatchObject({ Mw: 8, dia: "09", hhmm: "2330" });
    expect(isStale(done)).toBe(false);
  });

  it("ignores the answer to an edit that a newer edit replaced", async () => {
    const { states, report } = collect();
    let release: (res: Response) => void = () => {};
    const send = vi.fn(() => new Promise<Response>((resolve) => (release = resolve)));

    const cancel = requestEstimate(values, null, report, { fetch: send as never });
    await vi.advanceTimersByTimeAsync(400);
    cancel();
    release(Response.json(preview("Ilo")));
    await vi.advanceTimersByTimeAsync(0);

    expect(states.map((e) => e.state)).toEqual(["loading"]);
  });

  it("does not ask at all when an edit is replaced within the delay", async () => {
    const send = vi.fn(() => answer("Ilo"));

    const cancel = requestEstimate(values, null, () => {}, { fetch: send as never });
    cancel();
    await vi.advanceTimersByTimeAsync(1000);

    expect(send).not.toHaveBeenCalled();
  });

  it("keeps the previous result in view when the service fails", async () => {
    const { states, report } = collect();
    const previous: Result = {
      preview: preview("Callao"),
      input: { Mw: 7, h: 10, lat0: -12, lon0: -77, dia: "09", hhmm: "1200" },
    };
    const send = vi.fn(() => Promise.resolve(new Response("nope", { status: 502 })));

    requestEstimate(values, previous, report, { fetch: send as never });
    await vi.advanceTimersByTimeAsync(400);

    expect(states.at(-1)).toEqual({ state: "error", last: previous });
  });
});
