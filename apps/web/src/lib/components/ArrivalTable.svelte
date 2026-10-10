<script lang="ts">
  import type { components } from "@tsdhn/api-client";

  import { formatDuration, portArrivals } from "#lib/arrivals.js";

  type TravelTimes = components["schemas"]["TsunamiTravelResponse"];

  let {
    travelTimes,
    event,
    limit,
  }: {
    travelTimes: TravelTimes;
    event: { dia: string; hhmm: string };
    /** Show only the soonest ports until the reader asks for the rest. */
    limit?: number;
  } = $props();

  const all = $derived(portArrivals(travelTimes, event));
  let expanded = $state(false);
  const rows = $derived(limit && !expanded ? all.slice(0, limit) : all);
  const hidden = $derived(all.length - rows.length);
</script>

<table class="w-full text-sm">
  <caption class="sr-only">Llegada de la primera ola por puerto, de la más próxima a la más tardía</caption>
  <thead>
    <tr class="text-muted border-line border-b text-left text-xs">
      <th scope="col" class="py-2 font-medium">Puerto</th>
      <th scope="col" class="py-2 text-right font-medium">Llega en</th>
      <th scope="col" class="py-2 pl-4 text-right font-medium">Hora UTC</th>
      <th scope="col" class="hidden py-2 pl-4 text-right font-medium sm:table-cell">Distancia</th>
    </tr>
  </thead>
  <tbody class="num divide-line divide-y">
    {#each rows as row, i (row.port)}
      <tr>
        <th scope="row" class="py-2.5 text-left font-medium">{row.port}</th>
        <td class="py-2.5 text-right {i === 0 ? 'font-semibold' : ''}">{formatDuration(row.minutes)}</td>
        <td class="text-muted py-2.5 pl-4 text-right">
          {row.clock}{#if row.nextDay}<span class="ml-1 text-xs">+1 d</span>{/if}
        </td>
        <td class="text-muted hidden py-2.5 pl-4 text-right sm:table-cell">
          {row.distanceKm === null ? "" : `${Math.round(row.distanceKm).toLocaleString("es-PE")} km`}
        </td>
      </tr>
    {/each}
  </tbody>
</table>
{#if limit && all.length > limit}
  <button
    type="button"
    class="text-muted hover:text-ink flex min-h-11 items-center text-sm md:min-h-9"
    aria-expanded={expanded}
    onclick={() => (expanded = !expanded)}
  >
    {expanded ? "Mostrar menos" : `Ver ${hidden} puertos más`}
  </button>
{/if}
