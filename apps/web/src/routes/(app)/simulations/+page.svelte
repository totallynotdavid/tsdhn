<script lang="ts">
  import { goto, invalidateAll } from "$app/navigation";

  import PageHeader from "#lib/components/PageHeader.svelte";
  import ArrowIcon from "#lib/components/ui/ArrowIcon.svelte";
  import Status from "#lib/components/ui/Status.svelte";
  import { formatCoordinates, formatMagnitude, formatWhen } from "#lib/format.js";
  import { isInFlight } from "#lib/simulation-status.js";

  let { data } = $props();

  const watching = $derived(data.simulations.some((sim) => isInFlight(sim.status)));

  $effect(() => {
    if (!watching) return;
    const timer = setInterval(() => void invalidateAll(), 8000);
    return () => clearInterval(timer);
  });

  function onKeydown(event: KeyboardEvent) {
    const target = event.target as HTMLElement;
    const typing = target.closest("input, textarea, select, [contenteditable]");
    if (event.key === "n" && !typing && !event.metaKey && !event.ctrlKey && !event.altKey) {
      void goto("/new");
    }
  }
</script>

<svelte:head><title>Simulaciones · TSDHN</title></svelte:head>
<svelte:window onkeydown={onKeydown} />

<PageHeader>
  {#snippet title()}Simulaciones{/snippet}
</PageHeader>

<ul>
  {#each data.simulations as sim (sim.id)}
    <li>
      <a href="/simulations/{sim.id}" class="row gutter">
        <div class="main">
          <p class="t-label-lg num title">
            Mw {formatMagnitude(sim.magnitude)}
            <span class="muted coords">· {formatCoordinates(sim.latitude, sim.longitude)}</span>
          </p>
          <p class="t-body-sm muted detail">
            {#if sim.progress}
              {sim.progress.label}{sim.progress.position ? ` · ${sim.progress.position}` : ""}
            {:else}
              {sim.warning ?? "Sin estimado"}
            {/if}
          </p>
        </div>
        <div class="side">
          <Status status={sim.status} />
          <time
            class="t-body-sm muted"
            datetime={sim.createdAt.toISOString()}
            title={sim.createdAt.toLocaleString("es-PE")}
          >
            {formatWhen(sim.createdAt)}
          </time>
        </div>
        <ArrowIcon class="arrow" />
      </a>
    </li>
  {/each}
</ul>

<p class="t-body-sm muted shortcut gutter">
  Pulse <kbd class="t-mono-xs">N</kbd> para una nueva simulación.
</p>

<style>
  li + li {
    border-top: 1px solid var(--border-faint);
  }

  li:last-child {
    border-bottom: 1px solid var(--border-faint);
  }

  .row {
    display: flex;
    min-height: 72px;
    align-items: center;
    gap: 16px;
    padding-block: 14px;
    transition: background-color 0.15s;
  }

  .row:hover {
    background: var(--ink-alpha-2);
  }

  .main {
    min-width: 0;
    flex: 1;
  }

  .title,
  .detail {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .coords {
    font-weight: 400;
  }

  .muted {
    color: var(--ink-alpha-64);
  }

  .side {
    display: flex;
    flex-shrink: 0;
    flex-direction: column;
    align-items: flex-end;
    gap: 2px;
  }

  .row :global(.arrow) {
    display: none;
    flex-shrink: 0;
    color: var(--ink-alpha-48);
    transition:
      transform 0.2s,
      color 0.2s;
  }

  .row:hover :global(.arrow) {
    color: var(--ink);
    transform: translateX(2px);
  }

  .shortcut {
    display: none;
    margin-top: 16px;
  }

  kbd {
    padding: 2px 6px;
    border: 1px solid var(--border-muted);
    border-radius: 4px;
    background: var(--surface);
    color: var(--ink);
  }

  @media (min-width: 640px) {
    .row :global(.arrow) {
      display: block;
    }
  }

  @media (min-width: 768px) {
    .shortcut {
      display: block;
    }
  }
</style>
