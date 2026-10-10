<script lang="ts">
  import type { Snippet } from "svelte";

  type Tone = "info" | "warning" | "error";

  let {
    tone = "info",
    title,
    children,
  }: { tone?: Tone; title?: string; children?: Snippet } = $props();
</script>

<div class="alert {tone} t-body-md" role={tone === "error" ? "alert" : "status"}>
  {#if title}<p class="t-label-md title">{title}</p>{/if}
  {#if children}<div class="body" class:spaced={title}>{@render children()}</div>{/if}
</div>

<style>
  .alert {
    --marker: var(--heat-100);
    position: relative;
    padding: 12px 16px 12px 18px;
    border: 1px solid var(--border-faint);
    border-radius: 12px;
    background: var(--surface);
    color: var(--ink);
  }

  .alert::before {
    content: "";
    position: absolute;
    top: 12px;
    bottom: 12px;
    left: -1px;
    width: 2px;
    background: var(--marker);
  }

  .warning {
    --marker: var(--warn);
    border-color: var(--warn-line);
    background: var(--warn-soft);
  }

  .error {
    --marker: var(--danger);
    background: var(--danger-soft);
  }

  .body {
    overflow-wrap: anywhere;
  }

  .spaced {
    margin-top: 4px;
  }
</style>
