<script lang="ts">
  import type { components } from "@tsdhn/api-client";

  type Calculation = components["schemas"]["CalculationResponse"];

  let { calculation }: { calculation: Calculation } = $props();

  const rows = $derived([
    ["Longitud de ruptura", `${calculation.length.toFixed(1)} km`],
    ["Ancho de ruptura", `${calculation.width.toFixed(1)} km`],
    ["Dislocación", `${calculation.dislocation.toFixed(2)} m`],
    ["Momento sísmico", `${calculation.seismic_moment.toExponential(2)} N·m`],
    ["Azimut", `${calculation.azimuth.toFixed(1)}°`],
    ["Buzamiento", `${calculation.dip.toFixed(1)}°`],
    ["Distancia a la costa", `${calculation.distance_to_coast.toFixed(1)} km`],
    ["Ubicación del epicentro", calculation.epicenter_location],
  ] as const);
</script>

<div class="space-y-3">
  <div class="rounded-lg border border-brand-200 bg-brand-50 p-3 text-sm font-medium text-brand-900">
    {calculation.tsunami_warning}
  </div>
  <dl class="divide-y divide-neutral-100 rounded-lg border border-neutral-200 bg-white">
    {#each rows as [label, value] (label)}
      <div class="flex items-center justify-between px-4 py-2 text-sm">
        <dt class="text-neutral-500">{label}</dt>
        <dd class="font-medium text-neutral-900">{value}</dd>
      </div>
    {/each}
  </dl>
</div>
