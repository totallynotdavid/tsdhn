import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { followJob, type JobFrame } from "./job-stream";

/** Stands in for the browser's EventSource; the test plays the network. */
class FakeEventSource {
  static CLOSED = 2;
  static instances: FakeEventSource[] = [];

  readyState = 0;
  closed = false;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  close() {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }

  send(frame: Partial<JobFrame>) {
    this.onmessage?.({ data: JSON.stringify({ status: "running", outputs: [], ...frame }) });
  }

  /** The browser gave up on the connection, e.g. a refused connect. */
  refuse() {
    this.readyState = FakeEventSource.CLOSED;
    this.onerror?.();
  }
}

function follow() {
  const events: string[] = [];
  const stop = followJob(
    "/simulations/abc/events",
    {
      onFrame: (frame) => events.push(`frame:${frame.status}`),
      onReconnecting: (value) => events.push(`reconnecting:${value}`),
      onFinished: () => events.push("finished"),
      onGaveUp: () => events.push("gave up"),
    },
    { EventSource: FakeEventSource as never, retryMs: 5000, maxRetryMs: 60_000, maxRetries: 3 },
  );
  return { events, stop };
}

const latest = () => FakeEventSource.instances.at(-1)!;

beforeEach(() => {
  vi.useFakeTimers();
  FakeEventSource.instances = [];
});
afterEach(() => vi.useRealTimers());

describe("following a job", () => {
  it("passes progress frames on and stops when the job finishes", () => {
    const { events } = follow();

    latest().send({ status: "running" });
    latest().send({ status: "completed" });

    expect(events).toEqual(["frame:running", "frame:completed", "finished"]);
    expect(latest().closed).toBe(true);
  });

  it("ignores a frame it cannot read", () => {
    const { events } = follow();

    latest().onmessage?.({ data: "not json" });

    expect(events).toEqual([]);
  });

  it("reopens a refused connection after five seconds and says so meanwhile", () => {
    const { events } = follow();

    latest().refuse();

    expect(events).toEqual(["reconnecting:true"]);
    expect(FakeEventSource.instances).toHaveLength(1);

    vi.advanceTimersByTime(4999);
    expect(FakeEventSource.instances).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeEventSource.instances).toHaveLength(2);
    expect(latest().url).toBe("/simulations/abc/events");

    latest().onopen?.();
    latest().send({ status: "running" });
    expect(events).toEqual(["reconnecting:true", "reconnecting:false", "frame:running"]);
  });

  it("waits longer after each refusal and gives up after the last allowed retry", () => {
    const { events } = follow();

    // Refused at once, then after 5 s, 10 s and 20 s of waiting.
    for (const wait of [5000, 10_000, 20_000]) {
      latest().refuse();
      vi.advanceTimersByTime(wait - 1);
      const before = FakeEventSource.instances.length;
      vi.advanceTimersByTime(1);
      expect(FakeEventSource.instances).toHaveLength(before + 1);
    }
    expect(events).not.toContain("gave up");

    latest().refuse();
    vi.advanceTimersByTime(10 * 60_000);

    expect(FakeEventSource.instances).toHaveLength(4);
    expect(events.at(-2)).toBe("reconnecting:false");
    expect(events.at(-1)).toBe("gave up");
  });

  it("caps the wait", () => {
    followJob(
      "/x",
      { onFrame() {}, onReconnecting() {}, onFinished() {}, onGaveUp() {} },
      { EventSource: FakeEventSource as never, retryMs: 5000, maxRetryMs: 8000, maxRetries: 3 },
    );

    latest().refuse();
    vi.advanceTimersByTime(5000);
    latest().refuse();
    vi.advanceTimersByTime(8000);
    latest().refuse();
    vi.advanceTimersByTime(8000);

    expect(FakeEventSource.instances).toHaveLength(4);
  });

  it("counts only failures in a row", () => {
    const { events } = follow();

    for (let round = 0; round < 5; round++) {
      latest().refuse();
      vi.advanceTimersByTime(60_000);
      latest().onopen?.();
    }

    expect(events).not.toContain("gave up");
    expect(FakeEventSource.instances).toHaveLength(6);
  });

  it("leaves the browser to reopen a stream the relay ended", () => {
    const { events } = follow();

    // readyState stays CONNECTING while the browser retries on its own.
    latest().onerror?.();
    vi.advanceTimersByTime(60_000);

    expect(events).toEqual(["reconnecting:true"]);
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(latest().closed).toBe(false);
  });

  it("does not reopen after it is stopped", () => {
    const { events, stop } = follow();

    latest().refuse();
    stop();
    vi.advanceTimersByTime(60_000);

    expect(FakeEventSource.instances).toHaveLength(1);
    latest().refuse();
    expect(events).toEqual(["reconnecting:true"]);
  });
});
