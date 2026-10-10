<script lang="ts">
  import { goto, invalidateAll } from "$app/navigation";

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

<h1 class="mb-4 text-xl font-semibold">Simulaciones</h1>

<ul class="border-line bg-surface divide-line divide-y rounded-lg border">
  {#each data.simulations as sim (sim.id)}
    <li>
      <a
        href="/simulations/{sim.id}"
        class="hover:bg-canvas flex min-h-14 items-center justify-between gap-4 px-4 py-3 first:rounded-t-lg last:rounded-b-lg"
      >
        <div class="min-w-0">
          <p class="num truncate font-medium">
            Mw {formatMagnitude(sim.magnitude)}
            <span class="text-muted font-normal">· {formatCoordinates(sim.latitude, sim.longitude)}</span>
          </p>
          <p class="text-muted truncate text-xs">
            {#if sim.progress}
              {sim.progress.label}{sim.progress.position ? ` · ${sim.progress.position}` : ""}
            {:else}
              {sim.warning ?? "Sin estimado"}
            {/if}
          </p>
        </div>
        <div class="flex shrink-0 flex-col items-end gap-0.5">
          <Status status={sim.status} />
          <time
            class="text-muted text-xs"
            datetime={sim.createdAt.toISOString()}
            title={sim.createdAt.toLocaleString("es-PE")}
          >
            {formatWhen(sim.createdAt)}
          </time>
        </div>
      </a>
    </li>
  {/each}
</ul>

<p class="text-muted mt-3 hidden text-xs md:block">
  Pulse <kbd class="border-line-strong bg-surface rounded border px-1.5 py-0.5 font-sans">N</kbd> para una nueva simulación.
</p>
