<script lang="ts">
  import type { Snippet } from "svelte";

  type Tone = "info" | "success" | "warning" | "error";

  let {
    tone = "info",
    title,
    children,
  }: { tone?: Tone; title?: string; children?: Snippet } = $props();

  const tones: Record<Tone, string> = {
    info: "border-brand-200 bg-brand-50 text-brand-900",
    success: "border-green-200 bg-green-50 text-green-900",
    warning: "border-amber-200 bg-amber-50 text-amber-900",
    error: "border-red-200 bg-red-50 text-red-900",
  };
</script>

<div class="rounded-lg border p-4 text-sm {tones[tone]}" role="alert">
  {#if title}<p class="mb-1 font-semibold">{title}</p>{/if}
  {#if children}<div>{@render children()}</div>{/if}
</div>
