<script lang="ts">
  import { page } from "$app/state";

  import ErrorState from "#lib/components/ErrorState.svelte";
</script>

<main class="column">
  <ErrorState status={page.status} message={page.error?.message} />
</main>

<style>
  main {
    position: relative;
    display: flex;
    min-height: 100dvh;
    flex-direction: column;
    justify-content: center;
  }
</style>
