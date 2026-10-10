/** Return why preview mode must not start, or null when it may. */
export function previewRefusal(env: { NODE_ENV?: string; DATABASE_URL?: string }): string | null {
  if (env.NODE_ENV === "production") {
    return "Preview mode refuses to run with NODE_ENV=production.";
  }
  if (env.DATABASE_URL?.trim()) {
    return "Preview mode refuses to run with DATABASE_URL set; it uses its own embedded database.";
  }
  return null;
}
