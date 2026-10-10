<script lang="ts">
  import { statusMeta } from "#lib/simulation-status.js";

  import DotSpinner from "./DotSpinner.svelte";

  let { status }: { status: string } = $props();

  const meta = $derived(statusMeta(status));
</script>

<span class="status t-label-md">
  {#if meta.tone === "active"}
    <DotSpinner />
  {:else}
    <span class="mark {meta.tone}" aria-hidden="true"></span>
  {/if}
  {meta.label}
</span>

<style>
  .status {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: var(--ink);
    white-space: nowrap;
  }

  /* Same footprint as the spinner, so a row does not move when a job starts. */
  .mark {
    width: 8px;
    height: 8px;
    margin-inline: 6px;
    background: var(--ink-alpha-48);
  }

  .success {
    background: var(--ok);
  }

  .danger {
    background: var(--danger);
  }
</style>
