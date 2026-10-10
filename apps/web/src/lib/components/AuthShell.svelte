<script lang="ts">
  import type { Snippet } from "svelte";

  import favicon from "#lib/assets/favicon.svg";

  let {
    title,
    children,
    footer,
  }: { title: string; children: Snippet; footer: Snippet } = $props();
</script>

<main class="column shell">
  <div class="card">
    <img src={favicon} alt="" width="32" height="32" />
    <h1 class="t-h5">{title}</h1>
    <p class="t-body-md lead">Simulación de tsunamis a partir de un sismo.</p>
    <div class="body">{@render children()}</div>
  </div>
  <p class="t-body-md footer">{@render footer()}</p>
</main>

<style>
  .shell {
    position: relative;
    display: flex;
    min-height: 100dvh;
    flex-direction: column;
    justify-content: center;
    padding-block: 40px;
  }

  .card {
    width: 100%;
    max-width: 420px;
    margin-inline: auto;
    padding: 28px 24px;
    border-radius: 20px;
    background: var(--surface);
    box-shadow: var(--surface-shadow);
  }

  .lead {
    margin-top: 4px;
    color: var(--ink-alpha-64);
  }

  img {
    margin-bottom: 20px;
  }

  .body {
    margin-top: 24px;
  }

  .footer {
    margin-top: 32px;
    color: var(--ink-alpha-64);
    text-align: center;
  }

  .footer :global(a) {
    color: var(--heat-ink);
    font-weight: 450;
  }

  .footer :global(a:hover) {
    text-decoration: underline;
  }

  @media (min-width: 640px) {
    .card {
      padding: 36px 36px 32px;
    }
  }
</style>
