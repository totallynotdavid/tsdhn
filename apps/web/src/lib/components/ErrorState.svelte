<script lang="ts">
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

<section class="mx-auto max-w-md py-12 text-center sm:py-20">
  <p class="num text-muted text-sm font-medium">Error {status}</p>
  <h1 class="mt-2 text-xl font-semibold">{copy.title}</h1>
  <p class="text-muted mt-2 text-sm">{detail ? `${detail}. ` : ""}{copy.hint}</p>
  <div class="mt-6 flex flex-wrap justify-center gap-3">
    <Button href="/simulations">Ir a Simulaciones</Button>
    <Button href="/new" variant="secondary">Nueva simulación</Button>
  </div>
</section>
