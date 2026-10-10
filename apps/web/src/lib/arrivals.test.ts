import { describe, expect, it } from "vitest";

import { formatDuration, portArrivals } from "./arrivals";

const travel = {
  arrival_times: {
    "La Cruz": "02:56 23Oct",
    Arica: "00:19 23Oct",
    Callao: "01:41 23Oct",
  },
  distances: { "La Cruz": 2170.3, Arica: 225.8 },
  epicenter_info: {},
};

describe("port arrivals", () => {
  it("orders ports by arrival and measures time from the earthquake", () => {
    const rows = portArrivals(travel, { dia: "23", hhmm: "0000" });

    expect(rows.map((row) => row.port)).toEqual(["Arica", "Callao", "La Cruz"]);
    expect(rows.map((row) => row.minutes)).toEqual([19, 101, 176]);
    expect(rows[0]).toMatchObject({ clock: "00:19", nextDay: false, distanceKm: 225.8 });
    expect(rows[1].distanceKm).toBeNull();
  });

  it("counts waves that arrive on the next UTC day", () => {
    const rows = portArrivals(
      { arrival_times: { Ilo: "00:28 24Oct" }, distances: {}, epicenter_info: {} },
      { dia: "23", hhmm: "2330" },
    );

    expect(rows[0]).toMatchObject({ minutes: 58, nextDay: true });
  });

  it("handles the compute service's day overflow at month end", () => {
    const rows = portArrivals(
      { arrival_times: { Ilo: "00:28 32Oct" }, distances: {}, epicenter_info: {} },
      { dia: "31", hhmm: "2300" },
    );

    expect(rows[0].minutes).toBe(88);
  });

  it("ignores the month label, which is the service's own month", () => {
    const at = (text: string, dia: string, hhmm: string) =>
      portArrivals(
        { arrival_times: { Ilo: text }, distances: {}, epicenter_info: {} },
        { dia, hhmm },
      )[0];

    // Day 31 rolling to day 01 of the next month.
    expect(at("00:28 01Nov", "31", "2330")).toMatchObject({ minutes: 58, nextDay: true });
    // The service runs in a later month than the earthquake.
    expect(at("00:28 32Nov", "31", "2330")).toMatchObject({ minutes: 58, nextDay: true });
    expect(at("02:56 23Nov", "23", "0000")).toMatchObject({ minutes: 176, nextDay: false });
    // New year.
    expect(at("00:10 01Jan", "31", "2350")).toMatchObject({ minutes: 20, nextDay: true });
  });

  it("skips arrivals it cannot read", () => {
    const rows = portArrivals(
      { arrival_times: { Ilo: "n/a" }, distances: {}, epicenter_info: {} },
      { dia: "01", hhmm: "0000" },
    );

    expect(rows).toEqual([]);
  });
});

describe("duration", () => {
  it("reads in minutes, whole hours, or both", () => {
    expect(formatDuration(19)).toBe("19 min");
    expect(formatDuration(120)).toBe("2 h");
    expect(formatDuration(176)).toBe("2 h 56 min");
  });
});
