<script lang="ts">
  import type { components } from "@tsdhn/api-client";
  import type { ComponentProps } from "svelte";

  import Disclosure from "./ui/Disclosure.svelte";

  type Calculation = components["schemas"]["CalculationResponse"];

  let {
    calculation,
    variant,
  }: { calculation: Calculation; variant?: ComponentProps<typeof Disclosure>["variant"] } = $props();

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

<Disclosure summary="Parámetros de la fuente" {variant}>
  <dl class="num t-body-md rows">
    {#each rows as [label, value] (label)}
      <dt>{label}</dt>
      <dd>{value}</dd>
    {/each}
  </dl>
</Disclosure>

<style>
  .rows {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 6px 24px;
  }

  dt {
    color: var(--ink-alpha-64);
  }

  dd {
    text-align: right;
  }

  dd::first-letter {
    text-transform: uppercase;
  }
</style>
