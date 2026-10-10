<script lang="ts">
  import CornerArcs from "./CornerArcs.svelte";

  let { index, total, title, id }: { index: number; total: number; title: string; id?: string } = $props();

  const pad = (value: number) => String(value).padStart(2, "0");
</script>

<h2 {id} class="band label t-mono-xs">
  <CornerArcs />
  <span class="marker" aria-hidden="true"></span>
  <span class="position" aria-hidden="true">
    [ <span class="index">{pad(index)}</span> / {pad(total)} ] ·
  </span>
  <span class="title">{title}</span>
</h2>

<style>
  .label {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    font-weight: 400;
    user-select: none;
  }

  .marker {
    width: 2px;
    height: 16px;
    background: var(--heat-100);
  }

  .position {
    color: var(--ink-alpha-64);
    white-space: nowrap;
  }

  .index {
    color: var(--heat-ink);
  }

  .title {
    color: var(--ink);
    text-transform: uppercase;
  }

  @media (min-width: 640px) {
    .label {
      padding: 20px 32px;
    }
  }
</style>
