import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ execute: vi.fn() }));

vi.mock("#lib/server/db/index.js", () => ({ db: { execute: mocks.execute } }));
import { GET } from "./+server";

describe("health route", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("reports healthy when the database answers", async () => {
    mocks.execute.mockResolvedValue([{ "?column?": 1 }]);

    const response = await GET({} as never);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: "healthy", database_connected: true });
  });

  it("answers 503 when the database does not", async () => {
    mocks.execute.mockRejectedValue(new Error("connection refused"));

    const response = await GET({} as never);

    expect(response.status).toBe(503);
    expect(await response.json()).toEqual({ status: "degraded", database_connected: false });
  });
});
