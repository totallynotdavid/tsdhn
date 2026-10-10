<script lang="ts">
  import Header from "#lib/components/Header.svelte";

  let { data, children } = $props();
</script>

<a href="#contenido" class="skip t-label-md">Saltar al contenido</a>

<Header user={data.user} />
<main id="contenido" class="column">
  {@render children()}
</main>

<style>
  .skip {
    position: fixed;
    top: 8px;
    left: 8px;
    z-index: 130;
    padding: 8px 12px;
    border: 1px solid var(--control-border);
    border-radius: 10px;
    background: var(--surface);
    color: var(--ink);
    transform: translateY(-64px);
  }

  .skip:focus {
    transform: none;
  }

  main {
    position: relative;
    min-height: calc(100dvh - var(--header-height));
    padding-bottom: 80px;
  }
</style>
