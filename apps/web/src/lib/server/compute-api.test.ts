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

  it("creates an authenticated client", () => {
    const fetch = vi.fn();

    expect(computeClient(fetch)).toMatchObject({
      GET: expect.any(Function),
      POST: expect.any(Function),
    });
  });

  it("requires the compute URL when creating a client", () => {
    env.COMPUTE_API_URL = "";

    expect(() => computeClient(vi.fn())).toThrow("COMPUTE_API_URL is not set");
  });

  it("requires the compute token when creating a client", () => {
    env.COMPUTE_API_TOKEN = "";

    expect(() => computeClient(vi.fn())).toThrow("COMPUTE_API_TOKEN is not set");
  });

  it("returns the normalized request configuration", () => {
    expect(computeRequestConfig()).toEqual({
      url: "https://compute.example",
      headers: { Authorization: "Bearer token" },
    });
  });

  it("requires the compute URL in request configuration", () => {
    env.COMPUTE_API_URL = "";

    expect(() => computeRequestConfig()).toThrow("COMPUTE_API_URL is not set");
  });

  it("requires the compute token in request configuration", () => {
    env.COMPUTE_API_TOKEN = "";

    expect(() => computeRequestConfig()).toThrow("COMPUTE_API_TOKEN is not set");
  });
});
