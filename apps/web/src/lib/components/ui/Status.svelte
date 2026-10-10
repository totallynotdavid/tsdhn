<script lang="ts">
  import { statusMeta, type Tone } from "#lib/simulation-status.js";

  let { status }: { status: string } = $props();

  const meta = $derived(statusMeta(status));
  const dot: Record<Tone, string> = {
    neutral: "bg-muted/50",
    active: "bg-accent motion-safe:animate-pulse",
    success: "bg-ok",
    danger: "bg-danger",
  };
</script>

<span class="text-ink inline-flex items-center gap-2 text-sm whitespace-nowrap">
  <span class="size-2 rounded-full {dot[meta.tone]}" aria-hidden="true"></span>
  {meta.label}
</span>
