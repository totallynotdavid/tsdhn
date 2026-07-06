<script lang="ts">
  import { enhance } from "$app/forms";
  import Button from "$lib/components/ui/Button.svelte";
  import Alert from "$lib/components/ui/Alert.svelte";

  let { form } = $props();
  let loading = $state(false);
</script>

<svelte:head><title>Iniciar sesión · TSDHN</title></svelte:head>

<main class="flex min-h-screen items-center justify-center p-4">
  <div class="w-full max-w-sm space-y-6 rounded-2xl border border-neutral-200 bg-white p-8 shadow-sm">
    <div class="space-y-1 text-center">
      <h1 class="text-2xl font-bold text-neutral-900">TSDHN</h1>
      <p class="text-sm text-neutral-500">Pronóstico de tsunamis</p>
    </div>

    {#if form?.message}
      <Alert tone="error">{form.message}</Alert>
    {/if}

    <form
      method="POST"
      class="space-y-4"
      use:enhance={() => {
        loading = true;
        return async ({ update }) => {
          await update();
          loading = false;
        };
      }}
    >
      <label class="block space-y-1">
        <span class="text-sm font-medium text-neutral-700">Correo</span>
        <input
          name="email"
          type="email"
          required
          autocomplete="email"
          value={form?.email ?? ""}
          class="w-full rounded-lg border-neutral-300 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
        />
      </label>

      <label class="block space-y-1">
        <span class="text-sm font-medium text-neutral-700">Contraseña</span>
        <input
          name="password"
          type="password"
          required
          autocomplete="current-password"
          class="w-full rounded-lg border-neutral-300 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
        />
      </label>

      <Button type="submit" class="w-full" disabled={loading}>
        {loading ? "Ingresando…" : "Iniciar sesión"}
      </Button>
    </form>

    <p class="text-center text-sm text-neutral-500">
      ¿No tienes cuenta?
      <a href="/signup" class="font-medium text-brand-600 hover:underline">Crear cuenta</a>
    </p>
  </div>
</main>
