import createClient, { type Client } from "openapi-fetch";
import type { paths } from "./generated/schema";

export type { paths };
export type * from "./generated/schema";

export interface TsdhnClientOptions {
  baseUrl: string;
  serviceToken: string;
  fetch?: typeof globalThis.fetch;
}

/**
 * The service token must stay on the server and never reach the browser.
 */
export function createTsdhnClient(options: TsdhnClientOptions): Client<paths> {
  return createClient<paths>({
    baseUrl: options.baseUrl,
    fetch: options.fetch,
    headers: { Authorization: `Bearer ${options.serviceToken}` },
  });
}

export type TsdhnClient = Client<paths>;
