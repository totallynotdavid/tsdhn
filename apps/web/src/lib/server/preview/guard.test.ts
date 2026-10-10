import { describe, expect, it } from "vitest";

import { previewRefusal } from "./guard.js";

describe("previewRefusal", () => {
  it("allows development and test environments without a database URL", () => {
    expect(previewRefusal({})).toBeNull();
    expect(previewRefusal({ NODE_ENV: "development", DATABASE_URL: "" })).toBeNull();
    expect(previewRefusal({ NODE_ENV: "test", DATABASE_URL: "  " })).toBeNull();
  });

  it("refuses production", () => {
    expect(previewRefusal({ NODE_ENV: "production" })).toMatch(/NODE_ENV=production/);
  });

  it("refuses a real database URL", () => {
    expect(previewRefusal({ DATABASE_URL: "postgres://app@db/tsdhn" })).toMatch(/DATABASE_URL/);
  });
});
