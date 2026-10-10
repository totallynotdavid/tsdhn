import type { components } from "@tsdhn/api-client";

type TravelTimes = components["schemas"]["TsunamiTravelResponse"];

export interface PortArrival {
  port: string;
  /** Clock time of arrival in UTC, "HH:MM". */
  clock: string;
  /** Minutes from the earthquake to the first wave. */
  minutes: number;
  /** True when the wave arrives on a later UTC day than the earthquake. */
  nextDay: boolean;
  distanceKm: number | null;
}

// The compute service formats arrivals as "02:56 23Oct". Its month label is
// the service's own current month, not the earthquake's, and a wave that
// crosses midnight on the last day of a month gets day 32 or day 01. Only the
// clock and whether the day number moved are reliable.
const ARRIVAL = /^(\d{2}):(\d{2}) (\d{1,2})/;
const DAY_MINUTES = 1440;

/** Ports in order of arrival, soonest first. */
export function portArrivals(
  travel: TravelTimes,
  event: { dia: string; hhmm: string },
): PortArrival[] {
  const eventMinutes = Number(event.hhmm.slice(0, 2)) * 60 + Number(event.hhmm.slice(2, 4));
  const eventDay = Number(event.dia);

  const rows: PortArrival[] = [];
  for (const [port, text] of Object.entries(travel.arrival_times)) {
    const match = ARRIVAL.exec(text);
    if (!match) continue;
    const [, hh, mm, day] = match;
    const nextDay = Number(day) !== eventDay;
    rows.push({
      port,
      clock: `${hh}:${mm}`,
      minutes: (nextDay ? DAY_MINUTES : 0) + Number(hh) * 60 + Number(mm) - eventMinutes,
      nextDay,
      distanceKm: travel.distances[port] ?? null,
    });
  }
  return rows.sort((a, b) => a.minutes - b.minutes);
}

/** "19 min", "2 h", "2 h 56 min". */
export function formatDuration(minutes: number): string {
  const total = Math.max(0, Math.round(minutes));
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${m} min`;
}
