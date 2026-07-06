import { env } from "$env/dynamic/private";
import { createTsdhnClient, type TsdhnClient } from "@tsdhn/api-client";

export function backend(fetch: typeof globalThis.fetch): TsdhnClient {
  if (!env.BACKEND_URL) throw new Error("BACKEND_URL is not set");
  if (!env.BACKEND_SERVICE_TOKEN) throw new Error("BACKEND_SERVICE_TOKEN is not set");
  return createTsdhnClient({
    baseUrl: env.BACKEND_URL,
    serviceToken: env.BACKEND_SERVICE_TOKEN,
    fetch,
  });
}

export function backendRaw(): { url: string; headers: Record<string, string> } {
  if (!env.BACKEND_URL) throw new Error("BACKEND_URL is not set");
  if (!env.BACKEND_SERVICE_TOKEN) throw new Error("BACKEND_SERVICE_TOKEN is not set");
  return {
    url: env.BACKEND_URL.replace(/\/$/, ""),
    headers: { Authorization: `Bearer ${env.BACKEND_SERVICE_TOKEN}` },
  };
}
