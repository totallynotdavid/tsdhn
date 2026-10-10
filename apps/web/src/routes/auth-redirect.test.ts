import { isRedirect } from "@sveltejs/kit";
import { describe, expect, it, vi } from "vitest";

import { actions as loginActions, load as loginLoad } from "./login/+page.server";
import { actions as signupActions, load as signupLoad } from "./signup/+page.server";

// The real auth module reads private environment variables and a database.
vi.mock("#lib/server/auth.js", () => ({
  auth: { api: { signInEmail: vi.fn(), signUpEmail: vi.fn() } },
}));

function landing(run: () => unknown | Promise<unknown>): Promise<string> {
  return Promise.resolve()
    .then(run)
    .then(
      () => {
        throw new Error("expected a redirect");
      },
      (caught) => {
        if (!isRedirect(caught)) throw caught;
        return caught.location;
      },
    );
}

function url(redirectTo: string) {
  const target = new URL("https://web.example/login");
  target.searchParams.set("redirectTo", redirectTo);
  return target;
}

function submit(redirectTo: string) {
  const body = new URLSearchParams({ name: "Ana", email: "ana@example.com", password: "12345678" });
  return {
    request: new Request("https://web.example/login", { method: "POST", body }),
    url: url(redirectTo),
  };
}

const HOSTILE = ["/\t/evil.example", "/\n/evil.example", "//evil.example", "/\\evil.example"];

describe("where sign-in and sign-up send a user afterwards", () => {
  it("returns a signed-in visitor to the page they asked for", async () => {
    const context = { locals: { user: { id: "u" } }, url: url("/simulations/abc?x=1") };

    expect(await landing(() => loginLoad(context as never))).toBe("/simulations/abc?x=1");
    expect(await landing(() => signupLoad(context as never))).toBe("/simulations/abc?x=1");
  });

  it.each(HOSTILE)("keeps %j on this site", async (hostile) => {
    const context = { locals: { user: { id: "u" } }, url: url(hostile) };

    expect(await landing(() => loginLoad(context as never))).toBe("/");
    expect(await landing(() => signupLoad(context as never))).toBe("/");
    expect(await landing(() => loginActions.default(submit(hostile) as never))).toBe("/");
    expect(await landing(() => signupActions.default(submit(hostile) as never))).toBe("/");
  });
});
