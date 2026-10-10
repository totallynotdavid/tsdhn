<script lang="ts">
  import { enhance } from "$app/forms";
  import { invalidateAll } from "$app/navigation";
  import type { components } from "@tsdhn/api-client";

  import ArrivalTable from "#lib/components/ArrivalTable.svelte";
  import Map from "#lib/components/Map.svelte";
  import SourceDetails from "#lib/components/SourceDetails.svelte";
  import Alert from "#lib/components/ui/Alert.svelte";
  import Button from "#lib/components/ui/Button.svelte";
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
</script>

<svelte:head>
  <title>Mw {formatMagnitude(params.Mw)} · Simulaciones · TSDHN</title>
</svelte:head>

<a href="/simulations" class="text-muted hover:text-ink inline-flex min-h-11 items-center text-sm md:min-h-9">
  ← Simulaciones
</a>

<div class="mt-1 mb-6 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
  <div class="min-w-0">
    <h1 class="num text-xl font-semibold">
      Mw {formatMagnitude(params.Mw)}
      <span class="text-muted font-normal">· {formatCoordinates(params.lat0, params.lon0)}</span>
    </h1>
    <p class="text-muted mt-1 text-sm">
      {eventLabel} · creada <time datetime={data.sim.createdAt.toISOString()}>{formatWhen(data.sim.createdAt)}</time>
    </p>
  </div>
  <div class="flex items-center gap-3">
    <Status status={live.status} />
    {#if live.status === "completed"}
      <Button href="/new?from={data.sim.id}" variant="secondary">Repetir con otros datos</Button>
    {/if}
  </div>
</div>

<div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
  <div class="min-w-0 space-y-6">
    {#if canResubmit(live.status)}
      <Alert tone="error" title="No se envió al servicio de cálculo">
        La simulación quedó guardada, pero el servicio no la recibió. Puede enviarla de nuevo.
        {#if live.error}
          <details class="mt-2">
            <summary class="text-muted hover:text-ink min-h-6 cursor-pointer text-xs">Detalle técnico</summary>
            <pre class="mt-1 text-xs break-words whitespace-pre-wrap">{live.error}</pre>
          </details>
        {/if}
      </Alert>
      {#if form?.retryError}
        <Alert tone="error">{form.retryError}</Alert>
      {/if}
      <form method="POST" action="?/retry" use:enhance>
        <Button type="submit">Reintentar envío</Button>
      </form>
    {:else if live.status === "failed"}
      <Alert tone="error" title="La simulación falló">
        No se generaron los resultados. Puede intentarlo de nuevo con los mismos datos.
        {#if live.error}
          <details class="mt-2">
            <summary class="text-muted hover:text-ink min-h-6 cursor-pointer text-xs">Detalle técnico</summary>
            <pre class="mt-1 text-xs break-words whitespace-pre-wrap">{live.error}</pre>
          </details>
        {/if}
      </Alert>
      <Button href="/new?from={data.sim.id}">Intentar de nuevo</Button>
    {:else if !finished}
      <section aria-labelledby="progress-title" class="border-line bg-surface rounded-lg border p-4">
        <div class="flex items-baseline justify-between gap-3">
          <h2 id="progress-title" class="font-medium">{progress.label}</h2>
          {#if progress.position}<span class="num text-muted text-xs">Paso {progress.position}</span>{/if}
        </div>
        <div
          class="bg-line mt-3 h-1.5 overflow-hidden rounded-full"
          role="progressbar"
          aria-label="Avance de la simulación"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress.percent ?? undefined}
        >
          <div
            class="h-full rounded-full transition-[width] duration-500 {progress.percent === null
              ? 'bg-accent/30 w-full motion-safe:animate-pulse'
              : 'bg-accent'}"
            style:width={progress.percent === null ? undefined : `${progress.percent}%`}
          ></div>
        </div>
        <p class="text-muted mt-3 text-xs">
          Tarda cerca de una hora. Puede cerrar la página; el avance queda en Simulaciones.
          {#if reconnecting}<span class="text-warn-ink"> Reconectando…</span>{/if}
          {#if lostStream}
            <span class="text-warn-ink">
              Se perdió la conexión con el avance.
              <button
                type="button"
                class="text-accent min-h-11 font-medium hover:underline md:min-h-6"
                onclick={() => invalidateAll()}
              >
                Reintentar
              </button>
            </span>
          {/if}
        </p>
      </section>
    {:else if live.status === "completed"}
      <section aria-labelledby="files-title">
        <h2 id="files-title" class="mb-2 text-base font-semibold">Resultados</h2>
        {#if mainFiles.length === 0 && otherFiles.length === 0}
          <p class="text-muted text-sm">La simulación terminó, pero no dejó archivos.</p>
        {:else}
          <ul class="border-line bg-surface divide-line divide-y rounded-lg border">
            {#each mainFiles as [name, label, kind] (name)}
              <li>
                <a
                  href="/simulations/{data.sim.id}/outputs/{name}"
                  class="hover:bg-canvas flex min-h-12 items-center justify-between gap-4 px-4 py-2 first:rounded-t-lg last:rounded-b-lg"
                >
                  <span class="font-medium">{label}</span>
                  <span class="text-muted text-xs">{kind} ↓</span>
                </a>
              </li>
            {/each}
          </ul>
          {#if otherFiles.length > 0}
            <details class="mt-2">
              <summary class="text-muted hover:text-ink flex min-h-11 cursor-pointer items-center text-sm md:min-h-9">
                Otros archivos ({otherFiles.length})
              </summary>
              <ul class="divide-line border-line divide-y border-t">
                {#each otherFiles as file (file.name)}
                  <li>
                    <a
                      href="/simulations/{data.sim.id}/outputs/{file.name}"
                      class="hover:text-accent flex min-h-11 items-center justify-between gap-4 text-sm md:min-h-9"
                    >
                      {file.label}
                      <span class="text-muted text-xs">{file.kind} ↓</span>
                    </a>
                  </li>
                {/each}
              </ul>
            </details>
          {/if}
        {/if}
      </section>
    {/if}

    {#if arrivals.length > 0 && live.travelTimes}
      <section aria-labelledby="arrivals-title">
        <h2 id="arrivals-title" class="mb-1 text-base font-semibold">
          Llegada de la primera ola
          <span class="text-muted text-sm font-normal">
            · {arrivals[0].port} en {formatDuration(arrivals[0].minutes)}
          </span>
        </h2>
        <ArrivalTable travelTimes={live.travelTimes} event={when} />
      </section>
    {/if}

    {#if live.calculation}
      <SourceDetails calculation={live.calculation} />
    {/if}
  </div>

  <div class="lg:sticky lg:top-6 lg:self-start">
    <Map
      lat={params.lat0}
      lon={params.lon0}
      {faultCorners}
      interactive={false}
      zoom={5}
      class="h-60 lg:h-96"
    />
    <p class="text-muted mt-2 text-xs">
      {faultCorners ? "Epicentro y plano de falla (rectángulo azul)." : "Epicentro."}
    </p>
  </div>
</div>
