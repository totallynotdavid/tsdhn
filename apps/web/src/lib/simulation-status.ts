export type Tone = "neutral" | "active" | "success" | "danger";

export interface StatusMeta {
  label: string;
  tone: Tone;
}

const STATUS: Record<string, StatusMeta> = {
  submitting: { label: "Enviando", tone: "active" },
  submission_failed: { label: "No se envió", tone: "danger" },
  queued: { label: "En cola", tone: "neutral" },
  running: { label: "En curso", tone: "active" },
  completed: { label: "Lista", tone: "success" },
  failed: { label: "Falló", tone: "danger" },
};

export function statusMeta(status: string): StatusMeta {
  return STATUS[status] ?? { label: status, tone: "neutral" };
}

/** The status will not change by itself. */
export function isFinished(status: string): boolean {
  return status === "completed" || status === "failed" || status === "submission_failed";
}

/** The compute service never received the simulation, so it can be sent again. */
export function canResubmit(status: string): boolean {
  return status === "submitting" || status === "submission_failed";
}

/** A status that moves on its own and is worth watching. */
export function isInFlight(status: string): boolean {
  return status === "queued" || status === "running";
}

const STEP_LABEL: Record<string, string> = {
  fault_plane: "Plano de falla",
  deform: "Deformación del fondo marino",
  tsunami: "Propagación del tsunami",
  maxola: "Mapa de alturas máximas",
  ttt_max: "Mareogramas por puerto",
  ttt_inverso: "Grilla de tiempos de arribo",
  point_ttt: "Mapa de tiempos de arribo",
  copy_ttt_pdf: "Archivos finales",
};

export interface Progress {
  /** What the worker is doing now, in the user's words. */
  label: string;
  /** 0 to 100, or null when the worker has not started a step. */
  percent: number | null;
  /** "3 de 8", or null. */
  position: string | null;
}

export function progressOf(job: {
  status: string;
  step: string | null;
  stepIndex: number | null;
  totalSteps: number | null;
}): Progress {
  if (job.status === "submitting") {
    return { label: "Enviando al servicio de cálculo", percent: null, position: null };
  }
  if (job.status === "queued") {
    return { label: "Esperando su turno en la cola", percent: null, position: null };
  }
  const label = (job.step && STEP_LABEL[job.step]) || "Preparando el cálculo";
  if (job.stepIndex === null || !job.totalSteps) {
    return { label, percent: null, position: null };
  }
  return {
    label,
    // A step in progress counts as half done so the bar moves from the first step.
    percent: Math.round(((job.stepIndex - 0.5) / job.totalSteps) * 100),
    position: `${job.stepIndex} de ${job.totalSteps}`,
  };
}
