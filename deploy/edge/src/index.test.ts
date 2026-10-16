import { describe, expect, it } from "vitest";

import worker from "./index.ts";

describe("edge Worker", () => {
  it("forwards the public host and request headers to the web binding", async () => {
    let forwarded: Request | undefined;
    const response = await worker.fetch(
      new Request("https://tsdhn.caefisica.workers.dev/calculations?id=1", {
        headers: { "cf-connecting-ip": "203.0.113.7" },
      }),
      {
        WEB: {
          fetch(request) {
            forwarded = new Request(request);
            return Promise.resolve(new Response("ok"));
          },
          connect() {
            throw new Error("connect is not used by this test");
          },
        },
      },
    );

    expect(response.status).toBe(200);
    expect(forwarded?.url).toBe("http://tsdhn.caefisica.workers.dev/calculations?id=1");
    expect(forwarded?.headers.get("x-forwarded-for")).toBe("203.0.113.7");
    expect(forwarded?.headers.get("x-forwarded-proto")).toBe("https");
  });
});
