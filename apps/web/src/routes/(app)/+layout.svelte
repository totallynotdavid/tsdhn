<script lang="ts">
  import Navbar from "$lib/components/Navbar.svelte";
  import Footer from "$lib/components/Footer.svelte";

  let { data, children } = $props();
</script>

<div class="flex min-h-screen flex-col">
  <Navbar user={data.user} />
  <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6">
    {@render children()}
  </main>
  <Footer />
</div>
