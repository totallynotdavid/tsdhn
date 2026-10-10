<script lang="ts">
  import { untrack } from "svelte";
  import { superForm } from "sveltekit-superforms";
  import { zod4Client } from "sveltekit-superforms/adapters";

  import { formatDuration, portArrivals } from "#lib/arrivals.js";
  import ArrivalTable from "#lib/components/ArrivalTable.svelte";
  import Map from "#lib/components/Map.svelte";
  import SourceDetails from "#lib/components/SourceDetails.svelte";
  import Alert from "#lib/components/ui/Alert.svelte";
  import Button from "#lib/components/ui/Button.svelte";
  import Field from "#lib/components/ui/Field.svelte";
  import { type Estimate, isStale, requestEstimate, shownResult } from "#lib/estimate.js";
  import { earthquakeSchema } from "#lib/schema/earthquake.js";

  let { data } = $props();
  // Pass only the initial form value. superForm handles later server updates.
  const { form, errors, enhance, submitting, message } = superForm(untrack(() => data.form), {
    validators: zod4Client(earthquakeSchema),
    validationMethod: "oninput",
    resetForm: false,
  });

  let estimate = $state<Estimate>({ state: "incomplete" });
  let retry = $state(0);

  const parsed = $derived(earthquakeSchema.safeParse($form));

  $effect(() => {
    void retry;
    if (!parsed.success) {
      estimate = { state: "incomplete" };
      return;
    }
    const last = untrack(() => shownResult(estimate));
    return requestEstimate(parsed.data, last, (next) => (estimate = next));
  });

  // The newest result, or the previous one dimmed while an edit is pending.
  // It is always read with the event it was computed for, never the form's.
  const shown = $derived(shownResult(estimate));
  const stale = $derived(isStale(estimate));
  const arrivals = $derived(shown ? portArrivals(shown.preview.travel_times, shown.input) : []);
  const firstArrival = $derived(arrivals[0]);
  // The fault outline belongs to the epicenter it was computed for, so it is
  // drawn only while the marker still sits there.
  const faultCorners = $derived(
    estimate.state === "ready"
      ? estimate.result.preview.calculation.rectangle_corners.map((c) => ({ lat: c.lat, lon: c.lon }))
      : null,
  );

  // Enter in a number field moves nobody forward and would start an hour-long
  // job, so only Ctrl or Cmd with Enter submits from the keyboard.
  function onKeydown(event: KeyboardEvent) {
    if (event.key !== "Enter") return;
    const target = event.target as HTMLElement;
    if (!target.matches("input")) return;
    event.preventDefault();
    if (event.metaKey || event.ctrlKey) (event.currentTarget as HTMLFormElement).requestSubmit();
  }
</script>

<svelte:head><title>Nueva simulación · TSDHN</title></svelte:head>

<h1 class="mb-4 text-xl font-semibold">Nueva simulación</h1>

<div class="grid gap-6 lg:grid-cols-[24rem_minmax(0,1fr)]">
  <!-- The handler only reacts to keys pressed inside the form's own inputs. -->
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <form
    method="POST"
    use:enhance
    onkeydown={onKeydown}
    novalidate
    class="order-2 flex min-w-0 flex-col gap-6 lg:order-1"
  >
    <div class="grid grid-cols-2 gap-x-4 gap-y-4">
      <Field label="Magnitud (Mw)" error={$errors.magnitude}>
        {#snippet children(props)}
          <input
            {...props}
            name="magnitude"
            type="number"
            inputmode="decimal"
            step="0.1"
            bind:value={$form.magnitude}
            class="control num"
          />
        {/snippet}
      </Field>
      <Field label="Profundidad (km)" error={$errors.depth}>
        {#snippet children(props)}
          <input
            {...props}
            name="depth"
            type="number"
            inputmode="decimal"
            step="1"
            bind:value={$form.depth}
            class="control num"
          />
        {/snippet}
      </Field>
      <Field label="Latitud" error={$errors.latitude}>
        {#snippet children(props)}
          <input
            {...props}
            name="latitude"
            type="number"
            inputmode="decimal"
            step="0.0001"
            bind:value={$form.latitude}
            class="control num"
          />
        {/snippet}
      </Field>
      <Field label="Longitud" error={$errors.longitude}>
        {#snippet children(props)}
          <input
            {...props}
            name="longitude"
            type="number"
            inputmode="decimal"
            step="0.0001"
            bind:value={$form.longitude}
            class="control num"
          />
        {/snippet}
      </Field>
      <div class="col-span-2">
        <Field label="Fecha y hora del sismo (UTC)" error={$errors.datetime}>
          {#snippet children(props)}
            <input
              {...props}
              name="datetime"
              type="datetime-local"
              bind:value={$form.datetime}
              class="control num"
            />
          {/snippet}
        </Field>
      </div>
    </div>

    <section aria-labelledby="estimate-title" aria-live="polite" class="min-h-40">
      <div class="mb-2 flex items-baseline justify-between gap-3">
        <h2 id="estimate-title" class="text-base font-semibold">Estimado</h2>
        {#if estimate.state === "loading"}
          <span class="text-muted text-xs">Calculando…</span>
        {/if}
      </div>

      {#if estimate.state === "incomplete"}
        <p class="text-muted text-sm">
          Con los datos del sismo completos y válidos verá aquí cuándo llegaría la ola a cada puerto.
        </p>
      {:else if shown && firstArrival}
        <div class={stale ? "opacity-60 transition-opacity" : "transition-opacity"}>
          <p class="text-base">
            Primera llegada: <strong class="num">{firstArrival.port}</strong> en
            <strong class="num">{formatDuration(firstArrival.minutes)}</strong>
          </p>
          {#if shown.preview.calculation.tsunami_warning}
            <p class="text-muted mt-1 text-sm first-letter:uppercase">
              {shown.preview.calculation.tsunami_warning}
            </p>
          {/if}
          <div class="mt-3">
            <ArrivalTable travelTimes={shown.preview.travel_times} event={shown.input} limit={5} />
          </div>
          <SourceDetails calculation={shown.preview.calculation} />
        </div>
      {:else if estimate.state === "loading"}
        <div class="space-y-2" aria-hidden="true">
          <div class="bg-line h-5 w-3/4 animate-pulse rounded motion-reduce:animate-none"></div>
          <div class="bg-line h-4 w-1/2 animate-pulse rounded motion-reduce:animate-none"></div>
          <div class="bg-line h-24 animate-pulse rounded motion-reduce:animate-none"></div>
        </div>
      {/if}

      {#if estimate.state === "error"}
        <div class="mt-3">
          <Alert tone="error">
            No se pudo calcular el estimado.
            <button type="button" class="text-accent font-medium hover:underline" onclick={() => retry++}>
              Reintentar
            </button>
          </Alert>
        </div>
      {/if}
    </section>

    <div class="border-line bg-canvas sticky bottom-0 -mx-4 space-y-2 border-t px-4 py-3 sm:-mx-6 sm:px-6 lg:mx-0 lg:px-0">
      {#if $message}
        <Alert tone="error">{$message}</Alert>
      {/if}
      <Button type="submit" class="w-full" disabled={$submitting}>
        {$submitting ? "Iniciando…" : "Iniciar simulación"}
      </Button>
      <p class="text-muted text-xs">
        Tarda cerca de una hora. Puede cerrar la página; el progreso queda en Simulaciones.
      </p>
    </div>
  </form>

  <div class="order-1 lg:sticky lg:top-6 lg:order-2 lg:self-start">
    <Map
      bind:lat={$form.latitude}
      bind:lon={$form.longitude}
      {faultCorners}
      class="h-60 lg:h-[calc(100dvh-9rem)]"
    />
    <p class="text-muted mt-2 text-xs">Toque el mapa o arrastre el marcador para fijar el epicentro.</p>
  </div>
</div>
