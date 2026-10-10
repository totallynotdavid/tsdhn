<script lang="ts">
  import { page } from "$app/state";

  import ErrorState from "#lib/components/ErrorState.svelte";
</script>

<main class="mx-auto min-h-dvh max-w-6xl px-4 sm:px-6">
  <ErrorState status={page.status} message={page.error?.message} />
</main>
