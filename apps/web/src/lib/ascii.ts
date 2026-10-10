/** Maps a cell (x and y in 0..1, top-left origin) to an ink density in 0..1. */
export type AsciiShape = (x: number, y: number) => number;

const ramp = " .:-=+xX";

/** A stable pseudo-random value in 0..1 per cell. Integer arithmetic only, so the server and the browser print the same text. */
export function grain(column: number, row: number): number {
  let hash = Math.imul(column + 1, 0x27d4eb2d) ^ Math.imul(row + 1, 0x165667b1);
  hash = Math.imul(hash ^ (hash >>> 15), 0x85ebca6b);
  hash ^= hash >>> 13;
  return (hash >>> 0) / 0xffffffff;
}

/** A cell shows a glyph with probability equal to its density: thin regions read as specks, dense ones as texture. */
export function renderAscii(shape: AsciiShape, columns: number, rows: number): string {
  const lines: string[] = [];
  for (let row = 0; row < rows; row += 1) {
    let line = "";
    for (let column = 0; column < columns; column += 1) {
      const density = Math.min(1, shape(column / (columns - 1), row / (rows - 1)));
      if (density <= 0 || grain(column, row) >= density) {
        line += " ";
        continue;
      }
      const weight = density * (0.55 + 0.45 * grain(row, column));
      line += ramp[Math.max(1, Math.round(weight * (ramp.length - 1)))];
    }
    lines.push(line.trimEnd());
  }
  return lines.join("\n");
}

/** A rounded bump of height 1 centred on `center` with half-width `width`. */
function bump(x: number, center: number, width: number): number {
  const offset = (x - center) / width;
  return 1 / (1 + offset * offset);
}

/** Open water with a low swell on the left that gathers into one tall crest toward the right. */
export const waveShape: AsciiShape = (x, y) => {
  const crest =
    0.78 - 0.14 * bump(x, 0.22, 0.1) - 0.62 * bump(x, 0.7, 0.11) - 0.2 * bump(x, 0.9, 0.05);
  if (y < crest) return 0;
  return 0.12 + (0.88 * (y - crest)) / (1 - crest);
};
