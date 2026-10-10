import { beforeEach, describe, expect, it, vi } from "vitest";

const env = vi.hoisted(() => ({
  DATABASE_URL: "postgres://localhost/test" as string | undefined,
  TSDHN_PREVIEW: undefined as string | undefined,
}));

vi.mock("$app/env/private", () => ({
  get DATABASE_URL() {
    return env.DATABASE_URL;
  },
  get TSDHN_PREVIEW() {
    return env.TSDHN_PREVIEW;
  },
}));

describe("database configuration", () => {
  beforeEach(() => {
    env.DATABASE_URL = "postgres://localhost/test";
    env.TSDHN_PREVIEW = undefined;
    vi.resetModules();
  });

  it("opens an embedded database in preview mode without a database URL", async () => {
    env.TSDHN_PREVIEW = "1";
    env.DATABASE_URL = undefined;

    const { db } = await import("./index");
    const users = await db.select().from((await import("./schema")).user);

    expect(users.map((user) => user.email)).toEqual(["demo@tsdhn.test"]);
  });

  it("rejects an empty database URL", async () => {
    env.DATABASE_URL = "";

    await expect(import("./index")).rejects.toThrow("DATABASE_URL is not set");
  });
});
