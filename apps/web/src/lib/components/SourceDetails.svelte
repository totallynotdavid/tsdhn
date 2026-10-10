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
    ["Epicentro", calculation.epicenter_location],
  ] as const);
</script>

<details class="group border-line border-t py-3">
  <summary
    class="text-muted hover:text-ink flex min-h-11 cursor-pointer list-none items-center justify-between text-sm font-medium md:min-h-9 [&::-webkit-details-marker]:hidden"
  >
    Parámetros de la fuente
    <span aria-hidden="true" class="transition-transform group-open:rotate-90">›</span>
  </summary>
  <dl class="num mt-1 grid grid-cols-[1fr_auto] gap-x-6 gap-y-1.5 text-sm">
    {#each rows as [label, value] (label)}
      <dt class="text-muted">{label}</dt>
      <dd class="text-right first-letter:uppercase">{value}</dd>
    {/each}
  </dl>
</details>
