<script lang="ts">
  import { onMount } from "svelte";
  import { Map as MapLibre, Marker, NavigationControl, setWorkerUrl } from "maplibre-gl";
  import type { GeoJSONSource } from "maplibre-gl";
  import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
  import "maplibre-gl/dist/maplibre-gl.css";
  import type { FeatureCollection } from "geojson";

  export interface Corner {
    lat: number;
    lon: number;
  }

  let {
    lat = $bindable(-20.5),
    lon = $bindable(-70.5),
    faultCorners = null,
    interactive = true,
    zoom = 4,
    class: klass = "",
  }: {
    lat?: number | null;
    lon?: number | null;
    faultCorners?: Corner[] | null;
    /** Click or drag the marker to move the epicenter. */
    interactive?: boolean;
    zoom?: number;
    class?: string;
  } = $props();

  let container: HTMLDivElement;
  let map: MapLibre | undefined;
  let marker: Marker | undefined;
  let ready = $state(false);
  let failed = $state(false);

  const ACCENT = "#1f5fae";
  const empty: FeatureCollection = { type: "FeatureCollection", features: [] };

  function faultData(): FeatureCollection {
    if (!faultCorners || faultCorners.length < 3) return empty;
    const ring = faultCorners.map((c) => [c.lon, c.lat]);
    return {
      type: "FeatureCollection",
      features: [
        { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [ring] } },
      ],
    };
  }

  onMount(() => {
    setWorkerUrl(workerUrl);
    const start: [number, number] = [lon ?? -70.5, lat ?? -20.5];

    map = new MapLibre({
      container,
      style: "https://demotiles.maplibre.org/style.json",
      center: start,
      zoom,
      cooperativeGestures: true,
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    marker = new Marker({ color: ACCENT, draggable: interactive }).setLngLat(start).addTo(map);

    function moveTo(point: { lng: number; lat: number }) {
      lon = Number(point.lng.toFixed(2));
      lat = Number(point.lat.toFixed(2));
    }

    if (interactive) {
      map.on("click", (e) => moveTo(e.lngLat.wrap()));
      marker.on("dragend", () => moveTo(marker!.getLngLat().wrap()));
    }

    map.on("error", () => {
      if (!ready) failed = true;
    });

    map.on("load", () => {
      map!.addSource("fault", { type: "geojson", data: faultData() });
      map!.addLayer({
        id: "fault-fill",
        type: "fill",
        source: "fault",
        paint: { "fill-color": ACCENT, "fill-opacity": 0.2 },
      });
      map!.addLayer({
        id: "fault-line",
        type: "line",
        source: "fault",
        paint: { "line-color": ACCENT, "line-width": 2 },
      });
      ready = true;
    });

    return () => map?.remove();
  });

  $effect(() => {
    if (lon !== null && lat !== null) marker?.setLngLat([lon, lat]);
  });

  $effect(() => {
    const data = faultData();
    if (ready) (map?.getSource("fault") as GeoJSONSource | undefined)?.setData(data);
  });
</script>

<div class="border-line bg-line/40 relative overflow-hidden rounded-lg border {klass}">
  <!-- maplibre-gl.css is unlayered and sets position on its element, so size it from a wrapper. -->
  <div class="absolute inset-0">
    <div bind:this={container} class="size-full" role="application" aria-label="Mapa del epicentro"></div>
  </div>
  {#if !ready}
    <p class="text-muted pointer-events-none absolute inset-0 flex items-center justify-center px-6 text-center text-sm">
      {failed ? "No se pudo cargar el mapa. Las coordenadas se pueden escribir en el formulario." : "Cargando mapa…"}
    </p>
  {/if}
</div>
