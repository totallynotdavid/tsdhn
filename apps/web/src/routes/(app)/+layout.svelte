<script lang="ts">
  import Header from "#lib/components/Header.svelte";

  let { data, children } = $props();
</script>

<div class="flex min-h-dvh flex-col">
  <Header user={data.user} />
  <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
    {@render children()}
  </main>
</div>
