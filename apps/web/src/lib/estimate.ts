import type { components } from "@tsdhn/api-client";

import {
  type EarthquakeForm,
  type EarthquakeInput,
  toEarthquakeInput,
} from "#lib/schema/earthquake.js";

type Preview = components["schemas"]["CalculationPreview"];

/** A response together with the event it was computed for. */
export interface Result {
  preview: Preview;
  input: EarthquakeInput;
}

export type Estimate =
  | { state: "incomplete" }
  | { state: "loading"; last: Result | null }
  | { state: "ready"; result: Result }
  | { state: "error"; last: Result | null };

/** The result to show: the newest, or the previous one while a newer is pending. */
export function shownResult(estimate: Estimate): Result | null {
  if (estimate.state === "ready") return estimate.result;
  if (estimate.state === "loading" || estimate.state === "error") return estimate.last;
  return null;
}

export function isStale(estimate: Estimate): boolean {
  return estimate.state === "loading" || estimate.state === "error";
}

interface Options {
  fetch?: typeof fetch;
  /** Wait for the last edit to settle before asking. */
  delayMs?: number;
}

/**
 * Ask for an estimate of `values` once edits settle, reporting each state
 * change, the first at once. Returns a function that cancels the request. `last` is what stays
 * on screen, with the event it belongs to, until the new answer arrives.
 */
export function requestEstimate(
  values: EarthquakeForm,
  last: Result | null,
  report: (estimate: Estimate) => void,
  { fetch: send = fetch, delayMs = 400 }: Options = {},
): () => void {
  const input = toEarthquakeInput(values);
  const controller = new AbortController();
  // Whatever was on screen is out of date from the moment of the edit.
  report({ state: "loading", last });
  const timer = setTimeout(async () => {
    try {
      const res = await send("/api/calculations", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(values),
        signal: controller.signal,
      });
      if (!res.ok) throw new Error(String(res.status));
      const preview: Preview = await res.json();
      if (!controller.signal.aborted) report({ state: "ready", result: { preview, input } });
    } catch {
      if (!controller.signal.aborted) report({ state: "error", last });
    }
  }, delayMs);

  return () => {
    clearTimeout(timer);
    controller.abort();
  };
}
