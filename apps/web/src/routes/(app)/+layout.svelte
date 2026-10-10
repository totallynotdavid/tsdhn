<script lang="ts">
  import Header from "#lib/components/Header.svelte";

  let { data, children } = $props();
</script>

<a
  href="#contenido"
  class="bg-surface text-ink border-line-strong fixed top-2 left-2 z-50 -translate-y-16 rounded-md border px-3 py-2 text-sm font-medium focus:translate-y-0"
>
  Saltar al contenido
</a>

<div class="flex min-h-dvh flex-col">
  <Header user={data.user} />
  <main id="contenido" class="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
    {@render children()}
  </main>
</div>
