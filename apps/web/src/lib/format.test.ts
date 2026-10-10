import { describe, expect, it } from "vitest";

import { formatCoordinates, formatWhen } from "./format";

describe("formatting", () => {
  it("writes coordinates with hemispheres", () => {
    expect(formatCoordinates(-20.5, -70.5)).toBe("20.5°S 70.5°O");
    expect(formatCoordinates(10, 140.25)).toBe("10.0°N 140.3°E");
  });

  it("describes recent times relative to now and old ones as dates", () => {
    const now = new Date("2026-10-09T20:00:00Z");

    expect(formatWhen(new Date("2026-10-09T15:00:00Z"), now)).toBe("hace 5 h");
    expect(formatWhen(new Date("2026-10-09T19:59:40Z"), now)).toBe("ahora");
    expect(formatWhen(new Date("2026-09-01T12:00:00Z"), now)).toMatch(/2026/);
  });
});
