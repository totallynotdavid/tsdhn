<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    summary,
    variant = "row",
    children,
  }: {
    summary: string;
    /** `row` is a list row with a top rule; `inset` sits inside another surface and has no rule. */
    variant?: "row" | "inset";
    children: Snippet;
  } = $props();

  let open = $state(false);
  const id = $props.id();
</script>

<div class="disclosure {variant}">
  <button type="button" class="trigger t-label-md" aria-expanded={open} aria-controls="{id}-panel" onclick={() => (open = !open)}>
    {summary}
    <svg class="chevron" aria-hidden="true" viewBox="0 0 24 24" width="24" height="24" fill="none">
      <path
        d="M8.4001 10.2L12.0001 13.8L15.6001 10.2"
        stroke="currentColor"
        stroke-width="1.25"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  </button>
  <div class="panel" class:open id="{id}-panel" inert={!open}>
    <div class="clip">
      <div class="content">{@render children()}</div>
    </div>
  </div>
</div>

<style>
  .row {
    border-top: 1px solid var(--border-faint);
  }

  .trigger {
    display: flex;
    width: 100%;
    min-height: 44px;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding-block: 8px;
    color: var(--ink-alpha-64);
    text-align: left;
    transition: color 0.2s;
  }

  .trigger:hover {
    color: var(--ink);
  }

  .trigger:focus-visible {
    outline-offset: 2px;
  }

  .chevron {
    flex-shrink: 0;
    transition: transform 0.3s var(--ease-disclosure);
  }

  .trigger[aria-expanded="true"] .chevron {
    transform: rotate(180deg);
  }

  .panel {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows 0.3s var(--ease-disclosure);
  }

  .panel.open {
    grid-template-rows: 1fr;
  }

  .clip {
    min-height: 0;
    overflow: hidden;
  }

  .content {
    padding-bottom: 12px;
  }

  @media (min-width: 768px) {
    .trigger {
      min-height: 36px;
    }
  }
</style>
