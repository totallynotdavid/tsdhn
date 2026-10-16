import { beforeEach, describe, expect, it, vi } from "vitest";

const env = vi.hoisted(() => ({
  COMPUTE_API_TOKEN: "token",
  COMPUTE_API_URL: "https://compute.example/",
}));

vi.mock("$app/env/private", () => ({
  get COMPUTE_API_TOKEN() {
    return env.COMPUTE_API_TOKEN;
  },
  get COMPUTE_API_URL() {
    return env.COMPUTE_API_URL;
  },
}));

import { computeClient, computeRequestConfig } from "./compute-api";

describe("compute API configuration", () => {
  beforeEach(() => {
    env.COMPUTE_API_TOKEN = "token";
    env.COMPUTE_API_URL = "https://compute.example/";
  });

  it("returns the normalized request configuration", () => {
    expect(computeRequestConfig()).toEqual({
      url: "https://compute.example",
      headers: { Authorization: "Bearer token" },
    });
  });

  it.each([
    ["client", () => computeClient(vi.fn())],
    ["request configuration", () => computeRequestConfig()],
  ])("requires the compute URL and token for the %s", (_, build) => {
    env.COMPUTE_API_URL = "";
    expect(build).toThrow("COMPUTE_API_URL is not set");

    env.COMPUTE_API_URL = "https://compute.example/";
    env.COMPUTE_API_TOKEN = "";
    expect(build).toThrow("COMPUTE_API_TOKEN is not set");
  });
});
