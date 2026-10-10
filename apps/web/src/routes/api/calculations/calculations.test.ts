import { isHttpError } from "@sveltejs/kit";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ post: vi.fn() }));

vi.mock("#lib/server/compute-api.js", () => ({
  computeClient: () => ({ POST: mocks.post }),
}));

import { POST } from "./+server";

const VALID = {
  magnitude: 8.1,
  depth: 20,
  latitude: -12.1,
  longitude: -77.2,
  datetime: "2026-10-09T14:30",
};

function call(body: unknown, user: unknown = { id: "user-1" }) {
  return POST({
    request: new Request("https://web.example/api/calculations", {
      method: "POST",
      body: typeof body === "string" ? body : JSON.stringify(body),
    }),
    locals: { user },
    fetch: vi.fn(),
  } as never);
}

async function statusOf(run: ReturnType<typeof call>) {
  try {
    await run;
  } catch (caught) {
    if (isHttpError(caught)) return caught.status;
    throw caught;
  }
  throw new Error("expected an HTTP error");
}

describe("estimate endpoint", () => {
  beforeEach(() => vi.resetAllMocks());

  it("turns the form's UTC date and time into the compute service's day and clock fields", async () => {
    mocks.post.mockResolvedValue({ data: { calculation: {}, travel_times: {} } });

    const response = await call(VALID);

    expect(response.status).toBe(200);
    expect(mocks.post).toHaveBeenCalledWith("/api/v1/calculations", {
      body: { Mw: 8.1, h: 20, lat0: -12.1, lon0: -77.2, dia: "09", hhmm: "1430" },
    });
  });

  it("refuses a source outside the model domain before asking the compute service", async () => {
    expect(await statusOf(call({ ...VALID, longitude: 10 }))).toBe(400);
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("refuses a timestamp that names no real moment before asking the compute service", async () => {
    const statuses = await Promise.all(
      ["2026-99-99T99:99", "2026-02-31T10:00"].map((datetime) =>
        statusOf(call({ ...VALID, datetime })),
      ),
    );
    expect(statuses).toEqual([400, 400]);
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("refuses a body that is not JSON", async () => {
    expect(await statusOf(call("not json"))).toBe(400);
  });

  it("refuses a signed-out caller", async () => {
    expect(await statusOf(call(VALID, null))).toBe(401);
    expect(mocks.post).not.toHaveBeenCalled();
  });

  it("reports a gateway error when the compute service fails", async () => {
    mocks.post.mockResolvedValue({ error: { detail: "boom" } });

    expect(await statusOf(call(VALID))).toBe(502);
  });
});
