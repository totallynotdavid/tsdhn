import type { components } from "@tsdhn/api-client";

import type { EarthquakeInput } from "#lib/schema/earthquake.js";
import type { StoredOutput } from "#lib/server/db/compute.js";

type Calculation = components["schemas"]["CalculationResponse"];
type TravelTimes = components["schemas"]["TsunamiTravelResponse"];

export const DEMO_USER = {
  id: "preview-user",
  name: "Demo",
  email: "demo@tsdhn.test",
  password: "demo-preview",
};

/** The steps the real worker reports, in order. */
export const STEPS = [
  "fault_plane",
  "deform",
  "tsunami",
  "maxola",
  "ttt_max",
  "ttt_inverso",
  "point_ttt",
  "copy_ttt_pdf",
] as const;

export const OUTPUTS: Record<string, { filename: string; content_type: string; body: string }> = {
  input: { filename: "input.json", content_type: "application/json", body: '{"preview":true}\n' },
  runtime: {
    filename: "runtime.json",
    content_type: "application/json",
    body: '{"engine":"preview stub"}\n',
  },
  calculation: {
    filename: "calculation.json",
    content_type: "application/json",
    body: '{"preview":true}\n',
  },
  travel_times_json: {
    filename: "travel_times.json",
    content_type: "application/json",
    body: '{"preview":true}\n',
  },
  travel_times_csv: {
    filename: "travel_times.csv",
    content_type: "text/csv",
    body: "port,minutes\nPreview,0\n",
  },
  max_height_map: {
    filename: "maxola.pdf",
    content_type: "application/pdf",
    body: minimalPdf("Mapa de altura máxima (vista previa)"),
  },
  arrival_time_map: {
    filename: "ttt.pdf",
    content_type: "application/pdf",
    body: minimalPdf("Mapa de tiempos de arribo (vista previa)"),
  },
  mareogram: {
    filename: "mareograma.svg",
    content_type: "image/svg+xml",
    body: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 80"><polyline fill="none" stroke="#e5602b" stroke-width="2" points="0,40 30,40 50,10 70,70 90,25 110,55 130,35 160,42 200,40"/></svg>',
  },
};

export function storedOutputs(): StoredOutput[] {
  return Object.entries(OUTPUTS).map(([name, output]) => ({
    name,
    key: `preview/${name}`,
    filename: output.filename,
    content_type: output.content_type,
  }));
}

function minimalPdf(text: string): string {
  const ascii = text.normalize("NFD").replace(/[^\x20-\x7e]/g, "");
  const stream = `BT /F1 18 Tf 40 100 Td (${ascii}) Tj ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 360 200] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let body = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((object, index) => {
    offsets.push(body.length);
    body += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = body.length;
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) body += `${String(offset).padStart(10, "0")} 00000 n \n`;
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return body;
}

// Ports along the Peruvian and northern Chilean coast, as in the engine's station list.
const PORTS: [name: string, lat: number, lon: number][] = [
  ["Talara", -4.5751, -81.2827],
  ["Salaverry", -8.2279, -78.9818],
  ["Callao", -12.0689, -77.1667],
  ["Pisco", -13.8061, -76.2919],
  ["San Juan", -15.3556, -75.1603],
  ["Matarani", -17.001, -72.1088],
  ["Ilo", -17.6445, -71.3486],
  ["Arica", -18.4758, -70.3232],
];

const KM_PER_DEGREE = 111.2;
const WAVE_KM_PER_HOUR = 700;

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const rad = Math.PI / 180;
  const a =
    Math.sin(((lat2 - lat1) * rad) / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(((lon2 - lon1) * rad) / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(a));
}

function warningFor(magnitude: number, depth: number): string {
  if (depth > 60 || magnitude < 7) return "El epicentro esta en el Mar y NO genera Tsunami";
  if (magnitude >= 8.8) return "Genera un Tsunami grande y destructivo";
  if (magnitude >= 8.3995) return "Genera un Tsunami potencialmente destructivo";
  if (magnitude >= 7.9) return "Genera un Tsunami pequeno";
  return "Probable Tsunami pequeno y local";
}

/** The source parameters for an earthquake, from Wells and Coppersmith scaling. */
export function calculationFor(input: EarthquakeInput): Calculation {
  const length = 10 ** (-2.44 + 0.59 * input.Mw);
  const width = 10 ** (-1.01 + 0.32 * input.Mw);
  const moment = 10 ** (1.5 * input.Mw + 9.1);
  const dislocation = moment / (3e10 * length * 1e3 * width * 1e3);
  const azimuth = 340;
  const dip = 18;

  const strike = (azimuth * Math.PI) / 180;
  const along = length / 2;
  const across = (width * Math.cos((dip * Math.PI) / 180)) / 2;
  const cosLat = Math.cos((input.lat0 * Math.PI) / 180);
  const corner = (u: number, v: number) => ({
    lat: input.lat0 + (u * Math.cos(strike) - v * Math.sin(strike)) / KM_PER_DEGREE,
    lon: input.lon0 + (u * Math.sin(strike) + v * Math.cos(strike)) / (KM_PER_DEGREE * cosLat),
  });

  return {
    length,
    width,
    dislocation,
    seismic_moment: moment,
    tsunami_warning: warningFor(input.Mw, input.h),
    distance_to_coast: 62.4,
    azimuth,
    dip,
    epicenter_location: "mar",
    rectangle_parameters: { L: length * 1e3, W: width * 1e3, azimuth, dip },
    rectangle_corners: [
      corner(-along, -across),
      corner(along, -across),
      corner(along, across),
      corner(-along, across),
    ],
  };
}

/** Arrival times at the ports for an earthquake, from a constant wave speed. */
export function travelTimesFor(input: EarthquakeInput): TravelTimes {
  const start = Number(input.hhmm.slice(0, 2)) * 60 + Number(input.hhmm.slice(2, 4));
  const arrival_times: Record<string, string> = {};
  const distances: Record<string, number> = {};
  for (const [port, lat, lon] of PORTS) {
    const km = haversineKm(input.lat0, input.lon0, lat, lon);
    const at = start + Math.round((km / WAVE_KM_PER_HOUR) * 60);
    const day = Number(input.dia) + Math.floor(at / 1440);
    const clock = at % 1440;
    const hh = String(Math.floor(clock / 60)).padStart(2, "0");
    const mm = String(clock % 60).padStart(2, "0");
    arrival_times[port] = `${hh}:${mm} ${String(day).padStart(2, "0")}Oct`;
    distances[port] = Math.round(km * 10) / 10;
  }
  return {
    arrival_times,
    distances,
    epicenter_info: { latitud: String(input.lat0), longitud: String(input.lon0) },
  };
}
