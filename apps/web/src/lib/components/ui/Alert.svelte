<script lang="ts">
  import type { Snippet } from "svelte";

  type Tone = "info" | "warning" | "error";

  let {
    tone = "info",
    title,
    children,
  }: { tone?: Tone; title?: string; children?: Snippet } = $props();

  const tones: Record<Tone, string> = {
    info: "border-line bg-surface text-ink",
    warning: "border-warn-line bg-warn-soft text-warn-ink",
    error: "border-danger/30 bg-danger-soft text-ink",
  };
</script>

<div class="rounded-lg border px-4 py-3 text-sm {tones[tone]}" role={tone === "error" ? "alert" : "status"}>
  {#if title}<p class="font-medium">{title}</p>{/if}
  {#if children}<div class="break-words {title ? 'mt-1' : ''}">{@render children()}</div>{/if}
</div>
