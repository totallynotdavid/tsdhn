<script lang="ts">
  import "./layout.css";
  import { navigating } from "$app/state";
  import favicon from "#lib/assets/favicon.svg";
  import PageRails from "#lib/components/PageRails.svelte";

  let { children } = $props();
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>

<PageRails />

{#if navigating.to}
  <div class="progress" role="progressbar" aria-label="Cargando">
    <div class="progress-bar"></div>
  </div>
{/if}

{@render children()}

<style>
  .progress {
    position: fixed;
    inset: 0 0 auto;
    z-index: 120;
    height: 2px;
    overflow: hidden;
    background: var(--heat-20);
  }

  .progress-bar {
    width: 33%;
    height: 100%;
    background: var(--heat-100);
    animation: sweep 1s var(--ease-panel) infinite;
  }

  @media (prefers-reduced-motion: reduce) {
    .progress-bar {
      width: 100%;
      animation: none;
    }
  }

  @keyframes sweep {
    from {
      transform: translateX(-100%);
    }

    to {
      transform: translateX(300%);
    }
  }
</style>
