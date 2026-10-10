<script lang="ts">
  import { enhance } from "$app/forms";
  import { page } from "$app/state";

  import favicon from "#lib/assets/favicon.svg";
  import Alert from "#lib/components/ui/Alert.svelte";
  import Button from "#lib/components/ui/Button.svelte";
  import Field from "#lib/components/ui/Field.svelte";

  let { form } = $props();
  let loading = $state(false);
</script>

<svelte:head><title>Crear cuenta · TSDHN</title></svelte:head>

<main class="mx-auto flex min-h-dvh w-full max-w-sm flex-col justify-center px-4 py-10">
  <img src={favicon} alt="" class="mb-6 size-8" />
  <h1 class="text-xl font-semibold">Crear cuenta</h1>
  <p class="text-muted mt-1 text-sm">Simulación de tsunamis a partir de un sismo.</p>

  <form
    method="POST"
    class="mt-8 space-y-4"
    use:enhance={() => {
      loading = true;
      return async ({ update }) => {
        await update({ reset: false });
        loading = false;
      };
    }}
  >
    {#if form?.message}
      <Alert tone="error">
        {form.message}
        {#if form.existing}
          <a href="/login{page.url.search}" class="text-accent font-medium hover:underline">
            Iniciar sesión
          </a>
        {/if}
      </Alert>
    {/if}

    <Field label="Nombre">
      {#snippet children(props)}
        <input
          {...props}
          name="name"
          type="text"
          required
          autocomplete="name"
          value={form?.name ?? ""}
          class="control"
        />
      {/snippet}
    </Field>

    <Field label="Correo">
      {#snippet children(props)}
        <input
          {...props}
          name="email"
          type="email"
          required
          autocomplete="email"
          value={form?.email ?? ""}
          class="control"
        />
      {/snippet}
    </Field>

    <Field label="Contraseña" hint="Al menos 8 caracteres.">
      {#snippet children(props)}
        <input
          {...props}
          name="password"
          type="password"
          required
          minlength={8}
          autocomplete="new-password"
          class="control"
        />
      {/snippet}
    </Field>

    <Button type="submit" class="w-full" disabled={loading}>
      {loading ? "Creando…" : "Crear cuenta"}
    </Button>
  </form>

  <p class="text-muted mt-6 text-sm">
    ¿Ya tiene cuenta?
    <a href="/login{page.url.search}" class="text-accent font-medium hover:underline">Iniciar sesión</a>
  </p>
</main>
