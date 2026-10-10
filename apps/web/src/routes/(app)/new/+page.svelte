<script lang="ts">
  import { untrack } from "svelte";
  import { superForm } from "sveltekit-superforms";
  import { zod4Client } from "sveltekit-superforms/adapters";

  import { formatDuration, portArrivals } from "#lib/arrivals.js";
  import ArrivalTable from "#lib/components/ArrivalTable.svelte";
  import Map from "#lib/components/Map.svelte";
  import PageHeader from "#lib/components/PageHeader.svelte";
  import SectionLabel from "#lib/components/SectionLabel.svelte";
  import SourceDetails from "#lib/components/SourceDetails.svelte";
  import Alert from "#lib/components/ui/Alert.svelte";
  import Button from "#lib/components/ui/Button.svelte";
  import DotSpinner from "#lib/components/ui/DotSpinner.svelte";
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

<PageHeader>
  {#snippet title()}Nueva simulación{/snippet}
  {#snippet description()}
    Indique el sismo o toque el mapa. El estimado muestra al instante cuándo llegaría la ola a cada
    puerto; al iniciar la simulación se generan además los mapas y mareogramas.
  {/snippet}
</PageHeader>

<div class="layout">
  <!-- The handler only reacts to keys pressed inside the form's own inputs. -->
  <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
  <form method="POST" use:enhance onkeydown={onKeydown} novalidate class="form">
    <SectionLabel index={1} total={2} title="Sismo" />
    <div class="block fields">
      <Field label="Magnitud (Mw)" hint="De 6.5 a 9.5" error={$errors.magnitude}>
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
      <Field label="Profundidad (km)" hint="Del foco, hasta 700" error={$errors.depth}>
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
      <Field label="Latitud" hint="Sur es negativo" error={$errors.latitude}>
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
      <Field label="Longitud" hint="Oeste es negativo" error={$errors.longitude}>
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
      <div class="wide">
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

    <SectionLabel index={2} total={2} title="Estimado" id="estimate-title" />
    <section aria-labelledby="estimate-title" aria-live="polite" class="block estimate">
      {#if estimate.state === "loading"}
        <p class="t-body-sm calculating"><DotSpinner /> Calculando…</p>
      {/if}

      {#if estimate.state === "incomplete"}
        <p class="t-body-md muted">
          Con los datos del sismo completos y válidos verá aquí cuándo llegaría la ola a cada puerto.
        </p>
      {:else if shown && firstArrival}
        <div class="result" class:stale>
          {#key `${firstArrival.port}-${firstArrival.minutes}`}
            <p class="t-body-lg swap">
              Primera llegada: <strong class="num">{firstArrival.port}</strong> en
              <strong class="num">{formatDuration(firstArrival.minutes)}</strong>
            </p>
          {/key}
          {#if shown.preview.calculation.tsunami_warning}
            <p class="t-body-md muted warning">{shown.preview.calculation.tsunami_warning}</p>
          {/if}
          <div class="table">
            <ArrivalTable travelTimes={shown.preview.travel_times} event={shown.input} limit={5} />
          </div>
          <SourceDetails calculation={shown.preview.calculation} />
        </div>
      {:else if estimate.state === "loading"}
        <div class="skeleton" aria-hidden="true">
          <div class="bar wide-bar"></div>
          <div class="bar mid-bar"></div>
          <div class="bar tall-bar"></div>
        </div>
      {/if}

      {#if estimate.state === "error"}
        <div class="error">
          <Alert tone="error">
            No se pudo calcular el estimado.
            <button type="button" class="retry" onclick={() => retry++}>Reintentar</button>
          </Alert>
        </div>
      {/if}
    </section>

    <p class="t-body-sm muted note">
      Tarda cerca de una hora. Puede cerrar la página; el progreso queda en Simulaciones.
      <span class="shortcut">Ctrl + Enter inicia la simulación desde un campo.</span>
    </p>
    <div class="submit">
      {#if $message}
        <Alert tone="error">{$message}</Alert>
      {/if}
      <Button type="submit" class="w-full" disabled={$submitting}>
        {$submitting ? "Iniciando…" : "Iniciar simulación"}
      </Button>
    </div>
  </form>

  <div class="mapcol">
    <Map
      bind:lat={$form.latitude}
      bind:lon={$form.longitude}
      {faultCorners}
      class="h-60 lg:h-[calc(100dvh-11rem)]"
    />
    <p class="t-body-sm muted caption">Toque el mapa o arrastre el marcador para fijar el epicentro.</p>
  </div>
</div>

<style>
  .layout {
    display: grid;
  }

  .form {
    display: flex;
    min-width: 0;
    flex-direction: column;
    order: 2;
  }

  .mapcol {
    order: 1;
    padding: 16px;
    border-bottom: 1px solid var(--border-faint);
  }

  .caption {
    margin-top: 8px;
  }

  .block {
    padding: 24px 16px;
  }

  .fields {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }

  .wide {
    grid-column: span 2;
  }

  .estimate {
    position: relative;
    min-height: 200px;
  }

  .muted {
    color: var(--ink-alpha-64);
  }

  /* Out of the flow, so the result below does not move when it appears. */
  .calculating {
    position: absolute;
    top: 8px;
    right: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--ink-alpha-64);
  }

  .result {
    transition: opacity 0.2s;
  }

  .result.stale {
    opacity: 0.6;
  }

  .swap {
    animation: swap-in 0.2s ease-out;
  }

  .warning {
    margin-top: 4px;
  }

  .warning::first-letter {
    text-transform: uppercase;
  }

  .table {
    margin-top: 12px;
  }

  .skeleton {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .bar {
    height: 20px;
    border-radius: 6px;
    background: linear-gradient(
      90deg,
      var(--ink-alpha-4) 40%,
      var(--ink-alpha-7) 50%,
      var(--ink-alpha-4) 60%
    );
    background-size: 200% 100%;
    animation: shimmer 1.6s linear infinite;
  }

  .wide-bar {
    width: 75%;
  }

  .mid-bar {
    width: 50%;
    height: 16px;
  }

  .tall-bar {
    height: 96px;
  }

  .error {
    margin-top: 12px;
  }

  .retry {
    color: var(--heat-ink);
    font-weight: 450;
  }

  .retry:hover {
    text-decoration: underline;
  }

  .note {
    padding-inline: 16px;
    margin-bottom: 16px;
  }

  .shortcut {
    display: none;
  }

  .submit {
    position: sticky;
    bottom: 0;
    z-index: 3;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 16px;
    border-top: 1px solid var(--border-faint);
    background: var(--background-base);
  }

  @keyframes swap-in {
    from {
      opacity: 0;
      filter: blur(2px);
      transform: translateX(10px);
    }
  }

  @keyframes shimmer {
    from {
      background-position-x: 100%;
    }

    to {
      background-position-x: -100%;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .bar {
      animation: none;
    }
  }

  @media (min-width: 640px) {
    .block,
    .note,
    .submit {
      padding-inline: 32px;
    }

    .mapcol {
      padding: 24px 32px;
    }
  }

  @media (min-width: 768px) {
    .shortcut {
      display: inline;
    }
  }

  @media (min-width: 996px) {
    .layout {
      grid-template-columns: 26rem minmax(0, 1fr);
    }

    .form {
      order: 1;
      border-right: 1px solid var(--border-faint);
    }

    .mapcol {
      position: sticky;
      top: var(--header-offset);
      order: 2;
      align-self: start;
      padding: 24px 32px 24px 24px;
      border-bottom: 0;
    }

    .block {
      padding-inline: 32px;
    }
  }
</style>
