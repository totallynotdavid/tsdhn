import { COMPUTE_API_TOKEN, COMPUTE_API_URL } from "$app/env/private";
import { createTsdhnClient, type TsdhnClient } from "@tsdhn/api-client";

export function computeClient(fetch: typeof globalThis.fetch): TsdhnClient {
  if (!COMPUTE_API_URL) throw new Error("COMPUTE_API_URL is not set");
  if (!COMPUTE_API_TOKEN) throw new Error("COMPUTE_API_TOKEN is not set");
  return createTsdhnClient({
    baseUrl: COMPUTE_API_URL,
    computeApiToken: COMPUTE_API_TOKEN,
    fetch,
  });
}

export function computeRequestConfig(): { url: string; headers: Record<string, string> } {
  if (!COMPUTE_API_URL) throw new Error("COMPUTE_API_URL is not set");
  if (!COMPUTE_API_TOKEN) throw new Error("COMPUTE_API_TOKEN is not set");
  return {
    url: COMPUTE_API_URL.replace(/\/$/, ""),
    headers: { Authorization: `Bearer ${COMPUTE_API_TOKEN}` },
  };
}
