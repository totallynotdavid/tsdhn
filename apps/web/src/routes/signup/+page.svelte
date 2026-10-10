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

<svelte:head><title>Crear cuenta · TSDHN</title></svelte:head>

<AuthShell title="Crear cuenta">
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
      <Alert tone="error">
        {form.message}
        {#if form.existing}
          <a href="/login{page.url.search}" class="link">Iniciar sesión</a>
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

  {#snippet footer()}
    ¿Ya tiene cuenta?
    <a href="/login{page.url.search}">Iniciar sesión</a>
  {/snippet}
</AuthShell>

<style>
  .form {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .link {
    color: var(--heat-ink);
    font-weight: 450;
  }

  .link:hover {
    text-decoration: underline;
  }
</style>
