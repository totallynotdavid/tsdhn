interface Env {
  WEB: Fetcher;
}

// VPC services accept only HTTP. Keep the public host because the web app
// checks form origins against the Host header.
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    url.protocol = "http:";
    const forwarded = new Request(url, request);
    const client = request.headers.get("cf-connecting-ip");
    if (client) forwarded.headers.set("x-forwarded-for", client);
    forwarded.headers.set("x-forwarded-proto", "https");
    return env.WEB.fetch(forwarded);
  },
} satisfies ExportedHandler<Env>;
