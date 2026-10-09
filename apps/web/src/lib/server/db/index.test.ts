import { beforeEach, describe, expect, it, vi } from "vitest";

const env = vi.hoisted(() => ({ DATABASE_URL: "postgres://localhost/test" }));

vi.mock("$app/env/private", () => ({
  get DATABASE_URL() {
    return env.DATABASE_URL;
  },
}));

describe("database configuration", () => {
  beforeEach(() => {
    env.DATABASE_URL = "postgres://localhost/test";
    vi.resetModules();
  });

  it("rejects an empty database URL", async () => {
    env.DATABASE_URL = "";

    await expect(import("./index")).rejects.toThrow("DATABASE_URL is not set");
  });
});
