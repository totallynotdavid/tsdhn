import { isHttpError, isRedirect } from "@sveltejs/kit";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { load as appLayoutLoad } from "./(app)/+layout.server";
import { load as newLoad } from "./(app)/new/+page.server";
import { load as listLoad } from "./(app)/simulations/+page.server";
import { load as simulationLoad } from "./(app)/simulations/[id]/+page.server";

const mocks = vi.hoisted(() => ({
  listSimulations: vi.fn(),
  getSimulation: vi.fn(),
}));

// The node test environment cannot load the Svelte components imported by
// superforms. These loads only need the values returned by superValidate.
vi.mock("sveltekit-superforms", () => ({
  message: vi.fn(),
  superValidate: async (data: unknown) => ({ data }),
}));
vi.mock("sveltekit-superforms/adapters", () => ({ zod4: () => "adapter" }));
// The real modules read private environment variables from SvelteKit.
vi.mock("#lib/server/compute-api.js", () => ({ computeClient: vi.fn() }));
vi.mock("#lib/server/submit-simulation.js", () => ({ submitSimulation: vi.fn() }));

async function expectHttpError(action: unknown, status: number) {
  try {
    await action;
    throw new Error("expected load to throw");
  } catch (caught) {
    expect(isHttpError(caught)).toBe(true);
    if (isHttpError(caught)) expect(caught.status).toBe(status);
  }
}

function expectRedirect(run: () => unknown, location: string) {
  try {
    run();
    throw new Error("expected load to redirect");
  } catch (caught) {
    expect(isRedirect(caught)).toBe(true);
    if (isRedirect(caught)) {
      expect(caught.status).toBe(303);
      expect(caught.location).toBe(location);
    }
  }
}

function context(overrides: Record<string, unknown> = {}) {
  return {
    params: { id: "sim-1" },
    url: new URL("https://web.example/"),
    locals: {
      user: { id: "user-1" },
      simulationRepository: {
        listSimulations: mocks.listSimulations,
        getSimulation: mocks.getSimulation,
      },
    },
    ...overrides,
  };
}

const PAST = {
  id: "sim-1",
  createdAt: new Date("2026-10-09T10:00:00Z"),
  status: "running",
  params: { Mw: 8.4, h: 25, lat0: -12.1, lon0: -77.2, dia: "09", hhmm: "0930" },
  calculation: { tsunami_warning: "alerta de tsunami" },
  step: "tsunami",
  stepIndex: 3,
  totalSteps: 8,
};

describe("app layout load", () => {
  it("sends a signed-out visitor to sign in and back to where they were going", () => {
    expectRedirect(
      () =>
        appLayoutLoad({
          locals: { user: null },
          url: new URL("https://web.example/simulations/abc?tab=1"),
        } as never),
      "/login?redirectTo=%2Fsimulations%2Fabc%3Ftab%3D1",
    );
  });

  it("gives the header only the name and email", () => {
    const result = appLayoutLoad({
      locals: { user: { id: "user-1", name: "Ana", email: "ana@example.com", image: "x" } },
      url: new URL("https://web.example/new"),
    } as never);

    expect(result).toEqual({ user: { name: "Ana", email: "ana@example.com" } });
  });
});

describe("simulation list load", () => {
  beforeEach(() => vi.resetAllMocks());

  it("requires authentication before reading simulations", async () => {
    await expectHttpError(listLoad({ locals: { user: null } } as never), 401);

    expect(mocks.listSimulations).not.toHaveBeenCalled();
  });

  it("sends a user with no simulations straight to the new-simulation form", async () => {
    mocks.listSimulations.mockResolvedValue([]);

    try {
      await listLoad(context() as never);
      throw new Error("expected a redirect");
    } catch (caught) {
      expect(isRedirect(caught)).toBe(true);
      if (isRedirect(caught)) expect(caught.location).toBe("/new");
    }
  });

  it("returns the signed-in user's simulations as rows without the result tables", async () => {
    mocks.listSimulations.mockResolvedValue([PAST]);

    const result = await listLoad(context() as never);

    expect(mocks.listSimulations).toHaveBeenCalledWith("user-1");
    expect(result).toEqual({
      simulations: [
        {
          id: "sim-1",
          createdAt: PAST.createdAt,
          status: "running",
          magnitude: 8.4,
          latitude: -12.1,
          longitude: -77.2,
          warning: "alerta de tsunami",
          progress: { label: "Propagación del tsunami", percent: 31, position: "3 de 8" },
        },
      ],
    });
  });
});

async function loadNewForm(path = "/new") {
  const result = (await newLoad(
    context({ url: new URL(`https://web.example${path}`) }) as never,
  )) as { form: { data: Record<string, unknown> & { datetime: string } } };
  return result.form;
}

describe("new simulation load", () => {
  beforeEach(() => vi.resetAllMocks());

  it("starts from a default source with the current time", async () => {
    const before = Date.now();
    const form = await loadNewForm();

    expect(form.data).toMatchObject({ magnitude: 7.5, latitude: -20.5, longitude: -70.5 });
    expect(Date.parse(`${form.data.datetime}:00Z`)).toBeGreaterThan(before - 120_000);
    expect(mocks.getSimulation).not.toHaveBeenCalled();
  });

  it("repeats the source of one of the user's own simulations", async () => {
    mocks.getSimulation.mockResolvedValue(PAST);

    const form = await loadNewForm("/new?from=sim-1");

    expect(mocks.getSimulation).toHaveBeenCalledWith("user-1", "sim-1");
    expect(form.data).toMatchObject({
      magnitude: 8.4,
      depth: 25,
      latitude: -12.1,
      longitude: -77.2,
      datetime: "2026-10-09T09:30",
    });
  });

  it("ignores a simulation that is not the user's", async () => {
    mocks.getSimulation.mockResolvedValue(undefined);

    const form = await loadNewForm("/new?from=someone-elses");

    expect(form.data).toMatchObject({ magnitude: 7.5, latitude: -20.5 });
  });
});

describe("simulation detail load", () => {
  beforeEach(() => vi.resetAllMocks());

  it("returns the owned simulation", async () => {
    mocks.getSimulation.mockResolvedValue(PAST);

    const result = await simulationLoad(context() as never);

    expect(result).toEqual({ sim: PAST });
    expect(mocks.getSimulation).toHaveBeenCalledWith("user-1", "sim-1");
  });

  it("returns not found when the simulation is not owned by the user", async () => {
    mocks.getSimulation.mockResolvedValue(undefined);

    await expectHttpError(simulationLoad(context() as never), 404);
  });
});
