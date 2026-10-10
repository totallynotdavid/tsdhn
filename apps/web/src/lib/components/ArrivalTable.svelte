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

<table class="t-body-md">
  <caption class="sr-only">Llegada de la primera ola por puerto, de la más próxima a la más tardía</caption>
  <thead>
    <tr class="t-label-xs head">
      <th scope="col">Puerto</th>
      <th scope="col" class="end">Llega en</th>
      <th scope="col" class="end">Hora UTC</th>
      <th scope="col" class="end distance">Distancia</th>
    </tr>
  </thead>
  <tbody class="num">
    {#each rows as row, i (row.port)}
      <tr>
        <th scope="row" class="t-label-md">{row.port}</th>
        <td class="end" class:first={i === 0}>{formatDuration(row.minutes)}</td>
        <td class="end muted">
          {row.clock}{#if row.nextDay}<span class="t-label-xs next">+1 d</span>{/if}
        </td>
        <td class="end muted distance">
          {row.distanceKm === null ? "" : `${Math.round(row.distanceKm).toLocaleString("es-PE")} km`}
        </td>
      </tr>
    {/each}
  </tbody>
</table>
{#if limit && all.length > limit}
  <button type="button" class="more t-label-md" aria-expanded={expanded} onclick={() => (expanded = !expanded)}>
    {expanded ? "Mostrar menos" : `Ver ${hidden} puertos más`}
  </button>
{/if}

<style>
  table {
    width: 100%;
    border-collapse: collapse;
  }

  th,
  td {
    padding: 10px 0;
    text-align: left;
  }

  .head {
    color: var(--ink-alpha-64);
  }

  .head th {
    padding-block: 8px;
    border-bottom: 1px solid var(--border-faint);
    font-weight: 450;
  }

  tbody tr + tr {
    border-top: 1px solid var(--border-faint);
  }

  .end {
    padding-left: 16px;
    text-align: right;
  }

  .first {
    font-weight: 600;
  }

  .muted {
    color: var(--ink-alpha-64);
  }

  .next {
    margin-left: 4px;
  }

  .distance {
    display: none;
  }

  .more {
    display: flex;
    min-height: 44px;
    align-items: center;
    color: var(--ink-alpha-64);
    transition: color 0.2s;
  }

  .more:hover {
    color: var(--ink);
  }

  @media (min-width: 640px) {
    .distance {
      display: table-cell;
    }
  }

  @media (min-width: 768px) {
    .more {
      min-height: 36px;
    }
  }
</style>
