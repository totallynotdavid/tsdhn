import { describe, expect, it } from "vitest";

import {
  defaultEarthquake,
  earthquakeFromInput,
  earthquakeSchema,
  toEarthquakeInput,
} from "./earthquake";

const valid = {
  magnitude: 8.0,
  depth: 12,
  latitude: -20.5,
  longitude: -70.5,
  datetime: "2026-08-30T23:45",
};

function errorsOf(overrides: Partial<typeof valid>): string[] {
  const result = earthquakeSchema.safeParse({ ...valid, ...overrides });
  return result.success ? [] : result.error.issues.map((issue) => issue.message);
}

describe("earthquake input", () => {
  it("reads the zone-less form timestamp as UTC", () => {
    const input = toEarthquakeInput({ ...valid, datetime: "2026-08-31T23:45" });

    expect(input).toEqual({
      Mw: 8.0,
      h: 12,
      lat0: -20.5,
      lon0: -70.5,
      dia: "31",
      hhmm: "2345",
    });
  });

  it("gives the same UTC fields in every host time zone", () => {
    const original = process.env.TZ;
    try {
      const results = ["America/Lima", "Asia/Tokyo"].map((zone) => {
        process.env.TZ = zone;
        return toEarthquakeInput({ ...valid, datetime: "2026-08-31T23:45" });
      });
      expect(results[0]).toEqual(results[1]);
    } finally {
      process.env.TZ = original;
    }
  });

  it("accepts a source inside the model domain", () => {
    expect(errorsOf({})).toEqual([]);
    expect(errorsOf({ longitude: 150 })).toEqual([]);
  });

  it("rejects a magnitude below the model minimum", () => {
    expect(errorsOf({ magnitude: 6.4 })).toEqual(["La magnitud mínima es 6.5 Mw"]);
  });

  it("rejects points outside the Pacific grid with a reason", () => {
    expect(errorsOf({ latitude: 70 })[0]).toMatch(/Fuera del dominio/);
    expect(errorsOf({ longitude: 10 })[0]).toMatch(/Pacífico/);
  });

  it("asks for a missing number instead of reporting a type error", () => {
    expect(errorsOf({ magnitude: null as never })).toEqual(["Indique la magnitud"]);
  });

  it("uses the request time as the default event time", () => {
    const now = new Date("2026-10-09T23:52:41Z");
    expect(defaultEarthquake(now).datetime).toBe("2026-10-09T23:52");
  });

  it("rejects timestamps that name no real moment", () => {
    const message = ["Indique la fecha y hora del evento"];
    for (const datetime of [
      "2026-99-99T99:99",
      "2026-02-31T10:00",
      "2026-10-09T24:00",
      "2026-10-09T10:60",
      "2026-10-09",
      "2026-10-09T10:00junk",
      "",
    ]) {
      expect(errorsOf({ datetime })).toEqual(message);
    }
  });

  it("accepts a real timestamp, with or without seconds", () => {
    expect(errorsOf({ datetime: "2024-02-29T00:00" })).toEqual([]);
    expect(errorsOf({ datetime: "2026-10-09T10:30:15" })).toEqual([]);
  });

  describe("repeating a stored source", () => {
    const stored = { Mw: 8.4, h: 25, lat0: -17.6, lon0: -71.9 };
    const when = (dia: string, hhmm: string, createdAt: string) =>
      earthquakeFromInput({ ...stored, dia, hhmm }, new Date(createdAt)).datetime;

    it("keeps the source and the event's day and time", () => {
      expect(
        earthquakeFromInput(
          { ...stored, dia: "09", hhmm: "2330" },
          new Date("2026-10-09T23:52:41Z"),
        ),
      ).toEqual({
        magnitude: 8.4,
        depth: 25,
        latitude: -17.6,
        longitude: -71.9,
        datetime: "2026-10-09T23:30",
      });
    });

    it("takes the latest month in which the day exists, up to the creation time", () => {
      expect(when("23", "0000", "2026-10-09T10:00:00Z")).toBe("2026-09-23T00:00");
      expect(when("31", "2300", "2026-12-01T10:00:00Z")).toBe("2026-10-31T23:00");
      expect(when("29", "1200", "2026-03-05T10:00:00Z")).toBe("2026-01-29T12:00");
      expect(when("31", "0100", "2026-01-02T10:00:00Z")).toBe("2025-12-31T01:00");
    });

    it("falls back to the creation time when the stored day or time is not real", () => {
      expect(when("00", "0000", "2026-10-09T10:00:41Z")).toBe("2026-10-09T10:00");
      expect(when("12", "9999", "2026-10-09T10:00:41Z")).toBe("2026-10-09T10:00");
      expect(when("12", "", "2026-10-09T10:00:41Z")).toBe("2026-10-09T10:00");
    });

    it("gives a form the schema accepts", () => {
      const form = earthquakeFromInput(
        { ...stored, dia: "31", hhmm: "2359" },
        new Date("2026-03-01T00:00:00Z"),
      );
      expect(earthquakeSchema.safeParse(form).success).toBe(true);
    });
  });
});
