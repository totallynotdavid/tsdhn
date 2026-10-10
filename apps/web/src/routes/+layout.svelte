<script lang="ts">
  import "./layout.css";
  import { navigating } from "$app/state";
  import favicon from "#lib/assets/favicon.svg";

  let { children } = $props();
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

{#if navigating.to}
  <div class="bg-accent/20 fixed inset-x-0 top-0 z-50 h-0.5 overflow-hidden" role="progressbar" aria-label="Cargando">
    <div class="bg-accent h-full w-1/3 motion-safe:animate-pulse"></div>
  </div>
{/if}

{@render children()}
