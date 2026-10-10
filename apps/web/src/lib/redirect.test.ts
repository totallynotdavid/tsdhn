import { describe, expect, it } from "vitest";

import { safeRedirectPath } from "./redirect";

describe("redirect target", () => {
  it("keeps a path on this site, with its query", () => {
    expect(safeRedirectPath("/simulations/abc?x=1")).toBe("/simulations/abc?x=1");
  });

  it("falls back for anything that could leave the site", () => {
    for (const value of ["https://evil.example", "//evil.example", "/\\evil.example", "", null]) {
      expect(safeRedirectPath(value, "/simulations")).toBe("/simulations");
    }
  });

  it("falls back for paths a browser reads as another host once it strips control characters", () => {
    for (const value of [
      "/\t/evil.example",
      "/\n/evil.example",
      "/\r/evil.example",
      "/\t\n\r/evil.example",
      "/\u0000/evil.example",
      "/\u007f/evil.example",
      "/ok\t",
    ]) {
      expect(safeRedirectPath(value, "/simulations")).toBe("/simulations");
    }
  });

  it("keeps an encoded control character, which the browser does not strip", () => {
    expect(safeRedirectPath("/new?from=a%09b")).toBe("/new?from=a%09b");
  });

  it("never resolves to another origin", () => {
    for (const value of ["/a/../../b", "/%2F/evil.example", "/?next=//evil.example", "/#//x"]) {
      const target = safeRedirectPath(value, "/simulations");
      expect(new URL(target, "https://app.example").origin).toBe("https://app.example");
    }
  });
});
