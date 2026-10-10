<script lang="ts">
  import { waveShape } from "#lib/ascii.js";
  import AsciiField from "#lib/components/AsciiField.svelte";
  import Button from "#lib/components/ui/Button.svelte";

  let { status, message }: { status: number; message?: string } = $props();

  const copy = $derived(
    status === 404
      ? {
          title: "No encontramos esa página",
          hint: "Revise el enlace o vuelva a sus simulaciones.",
        }
      : status === 401 || status === 403
        ? { title: "No tiene acceso a esta página", hint: "Inicie sesión con la cuenta que la creó." }
        : { title: "Algo salió mal", hint: "No es un problema de sus datos. Intente de nuevo en un momento." },
  );
  // Show custom 404 details because the default message adds no useful context.
  const detail = $derived(status === 404 && message && message !== "Not Found" ? message : null);
</script>

<svelte:head><title>{copy.title} · TSDHN</title></svelte:head>

<section class="error-state">
  <div class="art"><AsciiField shape={waveShape} columns={72} rows={12} /></div>
  <p class="t-mono-sm code">Error {status}</p>
  <h1 class="t-h4">{copy.title}</h1>
  <p class="t-body-lg hint">{detail ? `${detail}. ` : ""}{copy.hint}</p>
  <div class="buttons">
    <Button href="/simulations">Ir a Simulaciones</Button>
    <Button href="/new" variant="secondary">Nueva simulación</Button>
  </div>
</section>

<style>
  .error-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 48px 16px 24px;
    text-align: center;
  }

  .art {
    max-width: 100%;
    margin-bottom: 32px;
    overflow: hidden;
  }

  .code {
    color: var(--heat-ink);
  }

  h1 {
    margin-top: 8px;
  }

  .hint {
    max-width: 440px;
    margin-top: 8px;
    color: var(--ink-alpha-64);
  }

  .buttons {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 12px;
    margin-top: 28px;
  }
</style>
