<script lang="ts">
  import { enhance } from "$app/forms";
  import Button from "$lib/components/ui/Button.svelte";
  import Alert from "$lib/components/ui/Alert.svelte";

  let { form } = $props();
  let loading = $state(false);
</script>

<svelte:head><title>Crear cuenta · TSDHN</title></svelte:head>

<main class="flex min-h-screen items-center justify-center p-4">
  <div class="w-full max-w-sm space-y-6 rounded-2xl border border-neutral-200 bg-white p-8 shadow-sm">
    <div class="space-y-1 text-center">
      <h1 class="text-2xl font-bold text-neutral-900">Crear cuenta</h1>
      <p class="text-sm text-neutral-500">Acceso al sistema TSDHN</p>
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
        <span class="text-sm font-medium text-neutral-700">Nombre</span>
        <input
          name="name"
          type="text"
          required
          autocomplete="name"
          value={form?.name ?? ""}
          class="w-full rounded-lg border-neutral-300 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
        />
      </label>

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
          minlength={8}
          autocomplete="new-password"
          class="w-full rounded-lg border-neutral-300 text-sm shadow-sm focus:border-brand-500 focus:ring-brand-500"
        />
      </label>

      <Button type="submit" class="w-full" disabled={loading}>
        {loading ? "Creando…" : "Crear cuenta"}
      </Button>
    </form>

    <p class="text-center text-sm text-neutral-500">
      ¿Ya tienes cuenta?
      <a href="/login" class="font-medium text-brand-600 hover:underline">Iniciar sesión</a>
    </p>
  </div>
</main>
