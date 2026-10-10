import { z } from "zod";

/**
 * The model bathymetry spans these bounds. Outside them the compute service
 * still answers, by extrapolating, so the form rejects such points instead.
 */
export const MODEL_DOMAIN = {
  latitude: { min: -60, max: 61 },
  /** Longitudes between these limits fall outside the Pacific grid. */
  longitude: { westMax: -62, eastMin: 130 },
} as const;

export function isInModelLongitude(longitude: number): boolean {
  return longitude <= MODEL_DOMAIN.longitude.westMax || longitude >= MODEL_DOMAIN.longitude.eastMin;
}

const number = (required: string) => z.number({ error: required });

export const earthquakeSchema = z.object({
  magnitude: number("Indique la magnitud")
    .min(6.5, "La magnitud mínima es 6.5 Mw")
    .max(9.5, "La magnitud máxima es 9.5 Mw"),
  depth: number("Indique la profundidad")
    .min(0, "La profundidad no puede ser negativa")
    .max(700, "La profundidad máxima es 700 km"),
  latitude: number("Indique la latitud")
    .min(MODEL_DOMAIN.latitude.min, "Fuera del dominio del modelo: la latitud va de -60 a 61")
    .max(MODEL_DOMAIN.latitude.max, "Fuera del dominio del modelo: la latitud va de -60 a 61"),
  longitude: number("Indique la longitud")
    .min(-180, "La longitud debe estar entre -180 y 180")
    .max(180, "La longitud debe estar entre -180 y 180")
    .refine(isInModelLongitude, "Fuera del dominio del modelo: solo cubre el océano Pacífico"),
  datetime: z
    .string({ error: "Indique la fecha y hora del evento" })
    .refine(isRealDatetime, "Indique la fecha y hora del evento"),
});

/** "YYYY-MM-DDTHH:MM" naming a moment that exists: no month 99, no 31 February. */
function isRealDatetime(text: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:[0-5]\d(\.\d+)?)?$/.test(text)) return false;
  const minute = text.slice(0, 16);
  const when = new Date(`${minute}:00Z`);
  return !Number.isNaN(when.getTime()) && when.toISOString().slice(0, 16) === minute;
}

export type EarthquakeForm = z.infer<typeof earthquakeSchema>;

export interface EarthquakeInput {
  Mw: number;
  h: number;
  lat0: number;
  lon0: number;
  dia: string;
  hhmm: string;
}

/**
 * The compute API expects event day and time as UTC fields. The form value is
 * a zone-less `datetime-local` string that the form labels as UTC.
 */
export function toEarthquakeInput(values: EarthquakeForm): EarthquakeInput {
  const when = new Date(`${values.datetime.slice(0, 16)}:00Z`);
  const dia = String(when.getUTCDate()).padStart(2, "0");
  const hhmm =
    String(when.getUTCHours()).padStart(2, "0") + String(when.getUTCMinutes()).padStart(2, "0");
  return {
    Mw: values.magnitude,
    h: values.depth,
    lat0: values.latitude,
    lon0: values.longitude,
    dia,
    hhmm,
  };
}

/** A fresh default per request, so the time is never the server start time. */
export function defaultEarthquake(now = new Date()): EarthquakeForm {
  return {
    magnitude: 7.5,
    depth: 10,
    latitude: -20.5,
    longitude: -70.5,
    datetime: now.toISOString().slice(0, 16),
  };
}

/**
 * The form for repeating a stored source with the same event. The input keeps
 * only day and time, so the month is the latest one, up to `createdAt`, in
 * which that day exists. A stored day or time that is not real falls back to
 * `createdAt` itself.
 */
export function earthquakeFromInput(input: EarthquakeInput, createdAt: Date): EarthquakeForm {
  return {
    magnitude: input.Mw,
    depth: input.h,
    latitude: input.lat0,
    longitude: input.lon0,
    datetime: eventTime(input, createdAt).toISOString().slice(0, 16),
  };
}

function eventTime({ dia, hhmm }: EarthquakeInput, createdAt: Date): Date {
  const day = Number(dia);
  const hour = Number(hhmm.slice(0, 2));
  const minute = Number(hhmm.slice(2, 4));
  if (!/^\d{4}$/.test(hhmm) || !(day >= 1 && day <= 31) || hour > 23 || minute > 59) {
    return createdAt;
  }
  // Within a year, every day number exists in some month.
  for (let back = 0; back < 12; back++) {
    const candidate = new Date(
      Date.UTC(createdAt.getUTCFullYear(), createdAt.getUTCMonth() - back, day, hour, minute),
    );
    if (candidate.getUTCDate() === day && candidate <= createdAt) return candidate;
  }
  return createdAt;
}
