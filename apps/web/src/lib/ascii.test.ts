import { describe, expect, it } from "vitest";

import { grain, renderAscii, waveShape } from "./ascii";

describe("ascii field", () => {
  it("prints the same text on every call", () => {
    expect(renderAscii(waveShape, 60, 20)).toBe(renderAscii(waveShape, 60, 20));
  });

  it("keeps grain within 0..1", () => {
    for (let column = 0; column < 40; column += 1) {
      for (let row = 0; row < 40; row += 1) {
        const value = grain(column, row);
        expect(value).toBeGreaterThanOrEqual(0);
        expect(value).toBeLessThanOrEqual(1);
      }
    }
  });

  it("returns one line per row and never overflows the columns", () => {
    const lines = renderAscii(waveShape, 50, 12).split("\n");

    expect(lines).toHaveLength(12);
    expect(Math.max(...lines.map((line) => line.length))).toBeLessThanOrEqual(50);
  });

  it("draws nothing for an empty shape and fills a solid one", () => {
    expect(renderAscii(() => 0, 10, 4).trim()).toBe("");
    expect(
      renderAscii(() => 1, 40, 10)
        .replaceAll("\n", "")
        .trim().length,
    ).toBeGreaterThan(300);
  });

  it("leaves the sky empty and the deep water dense", () => {
    const lines = renderAscii(waveShape, 80, 24).split("\n");
    const ink = (line: string) => line.replaceAll(" ", "").length;

    expect(ink(lines[0])).toBe(0);
    expect(ink(lines[23])).toBeGreaterThan(ink(lines[12]));
  });

  it("raises the crest above the surrounding water", () => {
    expect(waveShape(0.7, 0.3)).toBeGreaterThan(0);
    expect(waveShape(0.4, 0.3)).toBe(0);
  });
});
