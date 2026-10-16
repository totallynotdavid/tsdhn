import { isHttpError } from "@sveltejs/kit";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  computeRequestConfig: vi.fn(),
  getSimulation: vi.fn(),
}));

vi.mock("#lib/server/compute-api.js", () => ({
  computeRequestConfig: mocks.computeRequestConfig,
}));
import { GET } from "../../routes/(app)/simulations/[id]/outputs/[name]/+server";

const SIM = { id: "sim-1", outputs: ["max_height_map"] };

function context(overrides: Record<string, unknown> = {}) {
  return {
    params: { id: "sim-1", name: "max_height_map" },
    locals: {
      user: { id: "user-1" },
      simulationRepository: { getSimulation: mocks.getSimulation },
    },
    fetch: vi.fn(),
    ...overrides,
  };
}

async function expectHttpError(action: unknown, status: number) {
  try {
    await action;
    throw new Error("expected handler to throw");
  } catch (caught) {
    expect(isHttpError(caught)).toBe(true);
    if (isHttpError(caught)) expect(caught.status).toBe(status);
  }
}

describe("output download route", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mocks.getSimulation.mockResolvedValue(SIM);
    mocks.computeRequestConfig.mockReturnValue({
      url: "https://compute.example",
      headers: { authorization: "Bearer token" },
    });
  });

  it("requires an authenticated user before querying the simulation", async () => {
    await expectHttpError(GET(context({ locals: { user: null } }) as never), 401);

    expect(mocks.getSimulation).not.toHaveBeenCalled();
  });

  it("returns not found without contacting compute for an unknown simulation", async () => {
    mocks.getSimulation.mockResolvedValue(undefined);

    await expectHttpError(GET(context() as never), 404);

    expect(mocks.computeRequestConfig).not.toHaveBeenCalled();
  });

  it("returns a controlled gateway error when compute does not redirect", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 500 }));
    const requestContext = context({ fetch });

    await expectHttpError(GET(requestContext as never), 502);
  });

  it("streams the stored file after ownership and output checks", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(null, {
          status: 307,
          headers: { location: "http://storage:9000/result.pdf?signature=x" },
        }),
      )
      .mockResolvedValueOnce(
        new Response("%PDF-1.7", {
          headers: {
            "content-type": "application/pdf",
            "content-length": "8",
            "content-disposition": 'attachment; filename="result.pdf"',
            "set-cookie": "storage=leak",
          },
        }),
      );

    const response = await GET(context({ fetch }) as never);

    expect(await response.text()).toBe("%PDF-1.7");
    expect(response.headers.get("content-type")).toBe("application/pdf");
    expect(response.headers.get("content-disposition")).toBe('attachment; filename="result.pdf"');
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(mocks.getSimulation).toHaveBeenCalledWith("user-1", "sim-1");
    expect(fetch).toHaveBeenNthCalledWith(
      1,
      "https://compute.example/api/v1/jobs/sim-1/outputs/max_height_map",
      { headers: { authorization: "Bearer token" }, redirect: "manual" },
    );
    expect(fetch).toHaveBeenNthCalledWith(2, "http://storage:9000/result.pdf?signature=x");
  });

  it("returns a controlled gateway error when storage does not return the file", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(null, {
          status: 307,
          headers: { location: "http://storage:9000/result.pdf" },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 403 }));

    await expectHttpError(GET(context({ fetch }) as never), 502);
  });
});
