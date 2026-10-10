import type { components } from "@tsdhn/api-client";

import { isFinished } from "#lib/simulation-status.js";

/** The progress stream's frame; field names follow the compute API. */
export interface JobFrame {
  status: string;
  details: string | null;
  step: string | null;
  step_index: number | null;
  total_steps: number | null;
  calculation: components["schemas"]["CalculationResponse"] | null;
  travel_times: components["schemas"]["TsunamiTravelResponse"] | null;
  error: string | null;
  outputs: string[];
}

interface Handlers {
  onFrame: (frame: JobFrame) => void;
  /** The stream dropped and is being reopened, or is back. */
  onReconnecting: (reconnecting: boolean) => void;
  /** The job reached a status that will not change. */
  onFinished: () => void;
  /** The stream cannot be reopened: the session ended, the job is gone, or the service stays down. */
  onGaveUp: () => void;
}

interface Options {
  EventSource?: typeof EventSource;
  /** First wait before reopening; each failure doubles it. */
  retryMs?: number;
  maxRetryMs?: number;
  /** Consecutive failed reopenings before giving up. */
  maxRetries?: number;
}

/**
 * Follow a job's progress until it finishes; returns a function that stops.
 * The browser reopens a stream the relay ended. One it gave up on is reopened
 * here with a growing wait, because a refused connection, an expired session
 * and a missing job look the same. After `maxRetries` failures in a row it
 * calls `onGaveUp`.
 */
export function followJob(
  url: string,
  { onFrame, onReconnecting, onFinished, onGaveUp }: Handlers,
  {
    EventSource: Source = EventSource,
    retryMs = 5000,
    maxRetryMs = 60_000,
    maxRetries = 6,
  }: Options = {},
): () => void {
  let source: EventSource | undefined;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;
  let stopped = false;
  let failures = 0;

  function open() {
    const current = new Source(url);
    source = current;
    current.onopen = () => {
      failures = 0;
      onReconnecting(false);
    };
    current.onmessage = (event) => {
      let frame: JobFrame;
      try {
        frame = JSON.parse(event.data);
      } catch {
        return;
      }
      onFrame(frame);
      if (isFinished(frame.status)) {
        stopped = true;
        current.close();
        onFinished();
      }
    };
    current.onerror = () => {
      if (stopped) return;
      onReconnecting(true);
      if (current.readyState !== Source.CLOSED) return;
      current.close();
      if (failures >= maxRetries) {
        stopped = true;
        onReconnecting(false);
        onGaveUp();
        return;
      }
      retryTimer = setTimeout(open, Math.min(retryMs * 2 ** failures, maxRetryMs));
      failures++;
    };
  }

  open();
  return () => {
    stopped = true;
    source?.close();
    clearTimeout(retryTimer);
  };
}
