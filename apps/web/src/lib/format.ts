/** "20.5°S 70.5°O". */
export function formatCoordinates(lat: number, lon: number): string {
  const ns = lat < 0 ? "S" : "N";
  const ew = lon < 0 ? "O" : "E";
  return `${Math.abs(lat).toFixed(1)}°${ns} ${Math.abs(lon).toFixed(1)}°${ew}`;
}

export function formatMagnitude(mw: number): string {
  return mw.toFixed(1);
}

const relative = new Intl.RelativeTimeFormat("es", { numeric: "auto", style: "short" });
const absolute = new Intl.DateTimeFormat("es-PE", { dateStyle: "medium", timeStyle: "short" });

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["day", 86_400_000],
  ["hour", 3_600_000],
  ["minute", 60_000],
];

/** "hace 5 h" for recent times, a date after a week. */
export function formatWhen(date: Date, now = new Date()): string {
  const diff = date.getTime() - now.getTime();
  if (Math.abs(diff) > 7 * 86_400_000) return absolute.format(date);
  for (const [unit, size] of UNITS) {
    if (Math.abs(diff) >= size) return relative.format(Math.round(diff / size), unit);
  }
  return "ahora";
}

export function formatDateTimeUtc(date: Date): string {
  const text = new Intl.DateTimeFormat("es-PE", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
    hour12: false,
  }).format(date);
  return `${text} UTC`;
}
