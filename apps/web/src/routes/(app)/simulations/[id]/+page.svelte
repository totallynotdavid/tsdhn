<script lang="ts">
  import { enhance } from "$app/forms";
  import { invalidateAll } from "$app/navigation";
  import type { components } from "@tsdhn/api-client";

  import ArrivalTable from "#lib/components/ArrivalTable.svelte";
  import Map from "#lib/components/Map.svelte";
  import PageHeader from "#lib/components/PageHeader.svelte";
  import SectionLabel from "#lib/components/SectionLabel.svelte";
  import SourceDetails from "#lib/components/SourceDetails.svelte";
  import Alert from "#lib/components/ui/Alert.svelte";
  import ArrowIcon from "#lib/components/ui/ArrowIcon.svelte";
  import Button from "#lib/components/ui/Button.svelte";
  import Disclosure from "#lib/components/ui/Disclosure.svelte";
  import Status from "#lib/components/ui/Status.svelte";
  import { formatDuration, portArrivals } from "#lib/arrivals.js";
  import { formatCoordinates, formatMagnitude, formatWhen } from "#lib/format.js";
  import { followJob } from "#lib/job-stream.js";
  import type { EarthquakeInput } from "#lib/schema/earthquake.js";
  import { canResubmit, isFinished, progressOf } from "#lib/simulation-status.js";

  type Calculation = components["schemas"]["CalculationResponse"];
  type TravelTimes = components["schemas"]["TsunamiTravelResponse"];

  interface Job {
    status: string;
    details: string | null;
    step: string | null;
    stepIndex: number | null;
    totalSteps: number | null;
    calculation: Calculation | null;
    travelTimes: TravelTimes | null;
    error: string | null;
    outputs: string[];
  }

  let { data, form } = $props();

  const params = $derived(data.sim.params as EarthquakeInput);

  function fromSnapshot(): Job {
    const sim = data.sim;
    return {
      status: sim.status,
      details: sim.details,
      step: sim.step,
      stepIndex: sim.stepIndex,
      totalSteps: sim.totalSteps,
      calculation: sim.calculation as Calculation | null,
      travelTimes: sim.travelTimes as TravelTimes | null,
      error: sim.error,
      outputs: sim.outputs,
    };
  }

  let live = $state<Job>(fromSnapshot());
  let reconnecting = $state(false);
  let lostStream = $state(false);

  const finished = $derived(isFinished(live.status));
  const progress = $derived(progressOf(live));
  const when = $derived({ dia: params.dia ?? "00", hhmm: params.hhmm ?? "0000" });
  const arrivals = $derived(live.travelTimes ? portArrivals(live.travelTimes, when) : []);
  const faultCorners = $derived(
    live.calculation?.rectangle_corners.map((c) => ({ lat: c.lat, lon: c.lon })) ?? null,
  );

  const MAIN_OUTPUTS: [name: string, label: string, kind: string][] = [
    ["max_height_map", "Mapa de altura máxima", "PDF"],
    ["arrival_time_map", "Mapa de tiempos de arribo", "PDF"],
    ["mareogram", "Mareogramas por puerto", "SVG"],
  ];
  const OTHER_OUTPUTS: Record<string, [label: string, kind: string]> = {
    travel_times_csv: ["Tiempos de arribo", "CSV"],
    travel_times_json: ["Tiempos de arribo", "JSON"],
    calculation: ["Parámetros de la fuente", "JSON"],
    input: ["Datos de entrada", "JSON"],
    runtime: ["Entorno de ejecución", "JSON"],
  };
  const mainNames = new Set(MAIN_OUTPUTS.map(([name]) => name));
  const mainFiles = $derived(MAIN_OUTPUTS.filter(([name]) => live.outputs.includes(name)));
  const otherFiles = $derived(
    live.outputs
      .filter((name) => !mainNames.has(name))
      .map((name) => ({ name, label: OTHER_OUTPUTS[name]?.[0] ?? name, kind: OTHER_OUTPUTS[name]?.[1] ?? "" })),
  );

  $effect(() => {
    const snapshot = fromSnapshot();
    live = snapshot;
    if (isFinished(snapshot.status) || canResubmit(snapshot.status)) return;

    const stop = followJob(`/simulations/${data.sim.id}/events`, {
      onFrame: (frame) => {
        live = {
          status: frame.status,
          details: frame.details,
          step: frame.step,
          stepIndex: frame.step_index,
          totalSteps: frame.total_steps,
          calculation: frame.calculation ?? live.calculation,
          travelTimes: frame.travel_times ?? live.travelTimes,
          error: frame.error,
          outputs: frame.outputs ?? [],
        };
      },
      onReconnecting: (value) => (reconnecting = value),
      onGaveUp: () => (lostStream = true),
      onFinished: () => void invalidateAll(),
    });
    return () => {
      stop();
      reconnecting = false;
      lostStream = false;
    };
  });

  const eventLabel = $derived(
    `Sismo del día ${when.dia} a las ${when.hhmm.slice(0, 2)}:${when.hhmm.slice(2)} UTC`,
  );

  const inProgress = $derived(!canResubmit(live.status) && live.status !== "failed" && !finished);
  const showResults = $derived(!canResubmit(live.status) && live.status === "completed");
  const hasArrivals = $derived(arrivals.length > 0 && !!live.travelTimes);
  // Include only rendered sections in the total.
  const sectionCount = $derived((inProgress || showResults ? 1 : 0) + (hasArrivals ? 1 : 0));
  const arrivalsIndex = $derived(sectionCount);
</script>

<svelte:head>
  <title>Mw {formatMagnitude(params.Mw)} · Simulaciones · TSDHN</title>
</svelte:head>

<PageHeader back={{ href: "/simulations", label: "Simulaciones" }}>
  {#snippet title()}
    Mw {formatMagnitude(params.Mw)}
    <span class="muted coords">· {formatCoordinates(params.lat0, params.lon0)}</span>
  {/snippet}
  {#snippet description()}
    {eventLabel} · creada
    <time datetime={data.sim.createdAt.toISOString()}>{formatWhen(data.sim.createdAt)}</time>
  {/snippet}
  {#snippet actions()}
    <Status status={live.status} />
    {#if live.status === "completed"}
      <Button href="/new?from={data.sim.id}" variant="secondary">Repetir con otros datos</Button>
    {/if}
  {/snippet}
</PageHeader>

<div class="layout">
  <div class="main">
    {#if canResubmit(live.status)}
      <div class="block stack">
        <Alert tone="error" title="No se envió al servicio de cálculo">
          La simulación quedó guardada, pero el servicio no la recibió. Puede enviarla de nuevo.
          {#if live.error}
            <Disclosure summary="Detalle técnico" variant="inset">
              <pre class="t-mono-xs trace">{live.error}</pre>
            </Disclosure>
          {/if}
        </Alert>
        {#if form?.retryError}
          <Alert tone="error">{form.retryError}</Alert>
        {/if}
        <form method="POST" action="?/retry" use:enhance>
          <Button type="submit">Reintentar envío</Button>
        </form>
      </div>
    {:else if live.status === "failed"}
      <div class="block stack">
        <Alert tone="error" title="La simulación falló">
          No se generaron los resultados. Puede intentarlo de nuevo con los mismos datos.
          {#if live.error}
            <Disclosure summary="Detalle técnico" variant="inset">
              <pre class="t-mono-xs trace">{live.error}</pre>
            </Disclosure>
          {/if}
        </Alert>
        <div><Button href="/new?from={data.sim.id}">Intentar de nuevo</Button></div>
      </div>
    {:else if !finished}
      <SectionLabel index={1} total={sectionCount} title="Avance" id="progress-title" />
      <section aria-labelledby="progress-title" class="block">
        <div class="progress-head">
          <p class="t-h5">{progress.label}</p>
          {#if progress.position}<span class="num t-body-sm muted">Paso {progress.position}</span>{/if}
        </div>
        <div
          class="track"
          role="progressbar"
          aria-label="Avance de la simulación"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress.percent ?? undefined}
        >
          <div
            class="fill"
            class:indeterminate={progress.percent === null}
            style:width={progress.percent === null ? undefined : `${progress.percent}%`}
          ></div>
        </div>
        <p class="t-body-sm muted progress-note">
          Tarda cerca de una hora. Puede cerrar la página; el avance queda en Simulaciones.
          {#if reconnecting}<span class="warn"> Reconectando…</span>{/if}
          {#if lostStream}
            <span class="warn">
              Se perdió la conexión con el avance.
              <button type="button" class="retry" onclick={() => invalidateAll()}>Reintentar</button>
            </span>
          {/if}
        </p>
      </section>
    {:else if live.status === "completed"}
      <SectionLabel index={1} total={sectionCount} title="Resultados" id="files-title" />
      <section aria-labelledby="files-title">
        {#if mainFiles.length === 0 && otherFiles.length === 0}
          <p class="t-body-md muted block">La simulación terminó, pero no dejó archivos.</p>
        {:else}
          <ul class="files">
            {#each mainFiles as [name, label, kind] (name)}
              <li>
                <a href="/simulations/{data.sim.id}/outputs/{name}" class="file">
                  <span class="t-label-lg">{label}</span>
                  <span class="kind t-mono-xs">{kind}</span>
                  <ArrowIcon class="download" />
                </a>
              </li>
            {/each}
          </ul>
          {#if otherFiles.length > 0}
            <div class="others">
              <Disclosure summary="Otros archivos ({otherFiles.length})" variant="inset">
                <ul>
                  {#each otherFiles as file (file.name)}
                    <li>
                      <a href="/simulations/{data.sim.id}/outputs/{file.name}" class="other t-body-md">
                        {file.label}
                        <span class="kind t-mono-xs">{file.kind}</span>
                      </a>
                    </li>
                  {/each}
                </ul>
              </Disclosure>
            </div>
          {/if}
        {/if}
      </section>
    {/if}

    {#if hasArrivals && live.travelTimes}
      <SectionLabel
        index={arrivalsIndex}
        total={sectionCount}
        title="Llegada de la primera ola"
        id="arrivals-title"
      />
      <section aria-labelledby="arrivals-title" class="block">
        <p class="t-body-lg first">
          {arrivals[0].port} en {formatDuration(arrivals[0].minutes)}
        </p>
        <ArrivalTable travelTimes={live.travelTimes} event={when} />
      </section>
    {/if}

    {#if live.calculation}
      <div class="source"><SourceDetails calculation={live.calculation} variant="inset" /></div>
    {/if}
  </div>

  <div class="mapcol">
    <Map
      lat={params.lat0}
      lon={params.lon0}
      {faultCorners}
      interactive={false}
      zoom={5}
      class="h-60 lg:h-96"
    />
    <p class="t-body-sm muted caption">
      {faultCorners ? "Epicentro y plano de falla (rectángulo naranja)." : "Epicentro."}
    </p>
  </div>
</div>

<style>
  .layout {
    display: grid;
  }

  .main {
    min-width: 0;
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

  .muted {
    color: var(--ink-alpha-64);
  }

  .coords {
    font-weight: 400;
  }

  .block {
    padding: 24px 16px;
  }

  .stack {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .trace {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .progress-head {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
  }

  .track {
    height: 6px;
    margin-top: 16px;
    overflow: hidden;
    border-radius: 3px;
    background: var(--ink-alpha-7);
  }

  .fill {
    height: 100%;
    border-radius: 3px;
    background: var(--heat-100);
    transition: width var(--duration-spring-snap) var(--ease-spring-snap);
  }

  .indeterminate {
    width: 100%;
    background: linear-gradient(90deg, var(--heat-24) 40%, var(--heat-100) 50%, var(--heat-24) 60%);
    background-size: 200% 100%;
    animation: shimmer 1.6s linear infinite;
  }

  .progress-note {
    margin-top: 16px;
  }

  .warn {
    color: var(--warn);
  }

  .retry {
    min-height: 44px;
    color: var(--heat-ink);
    font-weight: 450;
  }

  .retry:hover {
    text-decoration: underline;
  }

  .files li + li {
    border-top: 1px solid var(--border-faint);
  }

  .file {
    display: flex;
    min-height: 56px;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    transition: background-color 0.15s;
  }

  .file:hover {
    background: var(--ink-alpha-2);
  }

  .file :global(.download) {
    flex-shrink: 0;
    color: var(--ink-alpha-48);
    rotate: 90deg;
    transition:
      transform 0.2s,
      color 0.2s;
  }

  .file:hover :global(.download) {
    color: var(--ink);
    transform: translateX(2px);
  }

  .file .t-label-lg {
    flex: 1;
  }

  .kind {
    color: var(--ink-alpha-64);
  }

  .others {
    padding-inline: 16px;
    border-top: 1px solid var(--border-faint);
  }

  .other {
    display: flex;
    min-height: 44px;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    transition: color 0.2s;
  }

  .other:hover {
    color: var(--heat-ink);
  }

  .first {
    margin-bottom: 8px;
    font-weight: 450;
  }

  .source {
    padding-inline: 16px;
    border-top: 1px solid var(--border-faint);
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
    .indeterminate {
      animation: none;
      background: var(--heat-24);
    }
  }

  @media (min-width: 640px) {
    .block,
    .file,
    .others,
    .source {
      padding-inline: 32px;
    }

    .mapcol {
      padding: 24px 32px;
    }
  }

  @media (min-width: 996px) {
    .layout {
      grid-template-columns: minmax(0, 1fr) 26rem;
    }

    .main {
      order: 1;
      border-right: 1px solid var(--border-faint);
    }

    .mapcol {
      position: sticky;
      top: var(--header-offset);
      order: 2;
      align-self: start;
      padding: 24px;
      border-bottom: 0;
    }
  }
</style>
