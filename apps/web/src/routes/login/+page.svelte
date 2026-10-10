<script lang="ts">
  import { enhance } from "$app/forms";
  import { page } from "$app/state";

  import AuthShell from "#lib/components/AuthShell.svelte";
  import Alert from "#lib/components/ui/Alert.svelte";
  import Button from "#lib/components/ui/Button.svelte";
  import Field from "#lib/components/ui/Field.svelte";

  let { form } = $props();
  let loading = $state(false);
</script>

<svelte:head><title>Iniciar sesión · TSDHN</title></svelte:head>

<AuthShell title="Iniciar sesión en TSDHN">
  <form
    method="POST"
    class="form"
    use:enhance={() => {
      loading = true;
      return async ({ update }) => {
        await update({ reset: false });
        loading = false;
      };
    }}
  >
    {#if form?.message}
      <Alert tone="error">{form.message}</Alert>
    {/if}

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

    <Field label="Contraseña">
      {#snippet children(props)}
        <input
          {...props}
          name="password"
          type="password"
          required
          autocomplete="current-password"
          class="control"
        />
      {/snippet}
    </Field>

    <Button type="submit" class="w-full" disabled={loading}>
      {loading ? "Ingresando…" : "Iniciar sesión"}
    </Button>
  </form>

  {#snippet footer()}
    ¿No tiene cuenta?
    <a href="/signup{page.url.search}">Crear cuenta</a>
  {/snippet}
</AuthShell>

<style>
  .form {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
</style>
