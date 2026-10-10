const BASE = "http://site.invalid";

/**
 * A same-site path from a `redirectTo` parameter, or the fallback. Browsers
 * strip tab, CR and LF from URLs and read `\` as `/`, so "/\t/evil.example"
 * means another host; control characters and backslashes are refused.
 */
export function safeRedirectPath(value: string | null | undefined, fallback = "/"): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return fallback;
  if (/[\p{Cc}\\]/u.test(value)) return fallback;
  try {
    if (new URL(value, BASE).origin !== BASE) return fallback;
  } catch {
    return fallback;
  }
  return value;
}
