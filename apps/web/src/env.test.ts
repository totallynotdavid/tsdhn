import { afterEach, describe, expect, it, vi } from "vitest";

const names = [
  "ORIGIN",
  "BETTER_AUTH_SECRET",
  "DATABASE_URL",
  "COMPUTE_API_URL",
  "COMPUTE_API_TOKEN",
] as const;

describe("environment declarations", () => {
  it("validates configured values for every private variable", async () => {
    const variables = await loadVariables(false);
    const results = await Promise.all(
      names.map((name) => {
        const schema = variables[name].schema;
        expect(schema).toBeDefined();
        return schema!["~standard"].validate("configured");
      }),
    );

    for (const result of results) {
      expect(result).toEqual({ value: "configured" });
    }
  });

  it("uses safe defaults while building", async () => {
    const variables = await loadVariables(true);
    const defaults = {
      ORIGIN: "http://localhost:3000",
      BETTER_AUTH_SECRET: "tsdhn-build-secret",
      DATABASE_URL: "postgres://localhost/test",
      COMPUTE_API_URL: "http://localhost:8000",
      COMPUTE_API_TOKEN: "tsdhn-build-token",
    } as const;

    const results = await Promise.all(
      names.map(
        async (name) =>
          [name, await variables[name].schema!["~standard"].validate(undefined)] as const,
      ),
    );

    expect(Object.fromEntries(results)).toEqual(
      Object.fromEntries(names.map((name) => [name, { value: defaults[name] }])),
    );
  });
});

async function loadVariables(building: boolean) {
  vi.resetModules();
  vi.doMock("$app/env", () => ({ building }));
  return (await import("./env")).variables;
}

afterEach(() => {
  vi.doUnmock("$app/env");
  vi.resetModules();
});
