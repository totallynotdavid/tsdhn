<script lang="ts">
  import type { Snippet } from "svelte";

  import CornerConnector from "./CornerConnector.svelte";

  let {
    title,
    description,
    back,
    actions,
  }: {
    title: Snippet;
    description?: Snippet;
    /** A link above the title, for pages reached from a list. */
    back?: { href: string; label: string };
    actions?: Snippet;
  } = $props();
</script>

<header class="page-header">
  <div class="gutter inner">
    <div class="text">
      {#if back}
        <a href={back.href} class="back t-label-md">← {back.label}</a>
      {/if}
      <h1 class="t-h4 num">{@render title()}</h1>
      {#if description}
        <p class="t-body-lg description">{@render description()}</p>
      {/if}
    </div>
    {#if actions}
      <div class="actions">{@render actions()}</div>
    {/if}
  </div>
  <!-- The rule spans the page; the column's own rails stop at its connectors. -->
  <div class="rule" aria-hidden="true"></div>
  <CornerConnector class="corner start" />
  <CornerConnector class="corner end" />
</header>

<style>
  .page-header {
    position: relative;
    margin-bottom: 0;
  }

  .inner {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px 24px;
    padding-block: 28px;
  }

  .text {
    min-width: 0;
    max-width: 640px;
  }

  /* The 44px hit area is padded out with negative margins, so the link keeps its place. */
  .back {
    display: inline-flex;
    min-height: 44px;
    align-items: center;
    margin-block: -6px -2px;
    color: var(--ink-alpha-64);
    transition: color 0.2s;
  }

  .back:hover {
    color: var(--ink);
  }

  h1 {
    overflow-wrap: anywhere;
  }

  .description {
    margin-top: 8px;
    color: var(--ink-alpha-64);
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .rule {
    position: absolute;
    bottom: -1px;
    left: calc(50% - 50vw);
    width: 100vw;
    height: 1px;
    background: var(--border-faint);
  }

  .page-header :global(.corner) {
    position: absolute;
    bottom: -11px;
    contain: layout paint;
  }

  .page-header :global(.corner.start) {
    left: -10.5px;
  }

  .page-header :global(.corner.end) {
    right: -10.5px;
  }

  @media (min-width: 768px) {
    .back {
      min-height: 32px;
      margin-block: 0 4px;
    }
  }

  @media (min-width: 996px) {
    .inner {
      padding-block: 40px;
    }
  }
</style>
