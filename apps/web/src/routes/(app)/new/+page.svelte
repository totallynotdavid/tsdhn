<script lang="ts">
  import { superForm } from "sveltekit-superforms";
  import { toast } from "svelte-sonner";
  import type { components } from "@tsdhn/api-client";

  import { toEarthquakeInput } from "$lib/schema/earthquake";
  import Map from "$lib/components/Map.svelte";
  import SourceParams from "$lib/components/SourceParams.svelte";
  import Button from "$lib/components/ui/Button.svelte";
  import Alert from "$lib/components/ui/Alert.svelte";

  let { data } = $props();
  const { form, errors, enhance, submitting, message } = superForm(data.form);

  type Preview = components["schemas"]["CalculationPreview"];
  let preview = $state<Preview | null>(null);
  let previewing = $state(false);

  const faultCorners = $derived(
    preview?.calculation.rectangle_corners?.map((c) => ({ lat: c.lat, lon: c.lon })) ?? null,
  );

  async function runPreview() {
    previewing = true;
    preview = null;
    try {
      const res = await fetch("/api/calculations", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(toEarthquakeInput($form)),
      });
      if (!res.ok) throw new Error();
      preview = await res.json();
    } catch {
      toast.error("No se pudo calcular la vista previa.");
    } finally {
      previewing = false;
    }
  }

  const inputClass =
    "w-full rounded-lg border-neutral-300 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500";
</script>

<svelte:head><title>Nueva simulación · TSDHN</title></svelte:head>

<h1 class="mb-6 text-2xl font-bold text-neutral-900">Nueva simulación</h1>

<div class="grid grid-cols-1 gap-6 md:grid-cols-2">
  <div class="space-y-6">
    <div class="rounded-xl border border-neutral-200 bg-white p-6">
      <h2 class="mb-1 text-lg font-semibold text-neutral-900">Parámetros del evento</h2>
      <p class="mb-4 text-sm text-neutral-500">
        Ingrese los datos del sismo o haga clic en el mapa para fijar el epicentro.
      </p>

      {#if $message}
        <div class="mb-4"><Alert tone="error">{$message}</Alert></div>
      {/if}

      <form method="POST" use:enhance class="space-y-4">
        <label class="block space-y-1">
          <span class="text-sm font-medium text-neutral-700">Magnitud (Mw)</span>
          <input type="number" step="0.1" bind:value={$form.magnitude} class={inputClass} />
          {#if $errors.magnitude}<span class="text-xs text-red-600">{$errors.magnitude}</span>{/if}
        </label>

        <label class="block space-y-1">
          <span class="text-sm font-medium text-neutral-700">Profundidad (km)</span>
          <input type="number" step="0.1" bind:value={$form.depth} class={inputClass} />
          {#if $errors.depth}<span class="text-xs text-red-600">{$errors.depth}</span>{/if}
        </label>

        <div class="grid grid-cols-2 gap-4">
          <label class="block space-y-1">
            <span class="text-sm font-medium text-neutral-700">Latitud</span>
            <input type="number" step="0.0001" bind:value={$form.latitude} class={inputClass} />
            {#if $errors.latitude}<span class="text-xs text-red-600">{$errors.latitude}</span>{/if}
          </label>
          <label class="block space-y-1">
            <span class="text-sm font-medium text-neutral-700">Longitud</span>
            <input type="number" step="0.0001" bind:value={$form.longitude} class={inputClass} />
            {#if $errors.longitude}<span class="text-xs text-red-600">{$errors.longitude}</span>{/if}
          </label>
        </div>

        <label class="block space-y-1">
          <span class="text-sm font-medium text-neutral-700">Fecha y hora (UTC)</span>
          <input type="datetime-local" bind:value={$form.datetime} class={inputClass} />
          {#if $errors.datetime}<span class="text-xs text-red-600">{$errors.datetime}</span>{/if}
        </label>

        <div class="flex flex-wrap gap-3 pt-2">
          <Button type="button" variant="outline" onclick={runPreview} disabled={previewing}>
            {previewing ? "Calculando…" : "Calcular vista previa"}
          </Button>
          <Button type="submit" disabled={$submitting}>
            {$submitting ? "Iniciando…" : "Iniciar simulación"}
          </Button>
        </div>
        <p class="text-xs text-neutral-400">
          La simulación completa puede tardar alrededor de una hora. Podrá seguir su progreso
          desde el panel.
        </p>
      </form>
    </div>

    {#if preview}
      <div class="rounded-xl border border-neutral-200 bg-white p-6">
        <h2 class="mb-3 text-lg font-semibold text-neutral-900">Vista previa</h2>
        <SourceParams calculation={preview.calculation} />
      </div>
    {/if}
  </div>

  <div class="md:sticky md:top-6 md:self-start">
    <Map bind:lat={$form.latitude} bind:lon={$form.longitude} {faultCorners} />
    <p class="mt-2 text-center text-sm text-neutral-500">
      Haga clic en el mapa para seleccionar la ubicación del epicentro.
    </p>
  </div>
</div>
