<script lang="ts">
  import { goto, invalidateAll } from "$app/navigation";
  import { page } from "$app/state";
  import { DropdownMenu } from "bits-ui";

  import favicon from "#lib/assets/favicon.svg";
  import { authClient } from "#lib/auth-client.js";
  import CornerConnector from "#lib/components/CornerConnector.svelte";
  import Button from "#lib/components/ui/Button.svelte";

  let { user }: { user: { name: string; email: string } } = $props();

  let scrollY = $state(0);

  const compact = $derived(scrollY > 8);
  const onList = $derived(page.url.pathname.startsWith("/simulations"));
  const onNew = $derived(page.url.pathname === "/new");
  const initial = $derived((user.name || user.email).trim().charAt(0).toUpperCase());

  async function signOut() {
    await authClient.signOut();
    await invalidateAll();
    await goto("/login");
  }
</script>

<svelte:window bind:scrollY />

<!-- The header stays fixed while it compacts. The spacer preserves its layout height. -->
<header class="header" data-compact={compact ? "" : undefined}>
  <nav class="bar" aria-label="Principal">
    <a href="/" class="brand t-label-lg" aria-label="TSDHN, inicio">
      <img src={favicon} alt="" width="24" height="24" />
      <span class="brand-name">TSDHN</span>
    </a>

    <a href="/simulations" class="link t-label-md" aria-current={onList ? "page" : undefined}>
      Simulaciones
    </a>

    <div class="actions">
      {#if !onNew}
        <Button href="/new">Nueva simulación</Button>
      {/if}
      <DropdownMenu.Root>
        <DropdownMenu.Trigger class="avatar t-label-md" aria-label="Cuenta de {user.email}">
          {initial}
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content align="end" sideOffset={8} class="menu">
            <p class="t-body-sm menu-email">{user.email}</p>
            <DropdownMenu.Item onSelect={signOut} class="menu-item t-label-md">Cerrar sesión</DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </div>

    <CornerConnector class="connector start" />
    <CornerConnector class="connector end" />
  </nav>
  <div class="rule" aria-hidden="true"></div>
</header>
<div class="spacer" aria-hidden="true"></div>

<style>
  .header {
    --bar-height: var(--header-height);
    position: fixed;
    inset: 0 0 auto;
    z-index: 101;
    background: var(--background-base);
  }

  .header[data-compact] {
    --bar-height: 72px;
  }

  .bar {
    position: relative;
    display: flex;
    width: min(100% - 32px, var(--container-width));
    height: var(--bar-height);
    align-items: center;
    gap: 4px;
    margin-inline: auto;
    padding-inline: 16px;
    transition: height 0.2s;
  }

  /* Keep labels at 14px so the row fits a 390px screen. */
  .link,
  .actions :global(.button) {
    font-size: 14px;
    line-height: 20px;
  }

  .bar::before {
    content: "";
    position: absolute;
    inset: 0;
    border-inline: 1px solid var(--border-faint);
    pointer-events: none;
  }

  .rule {
    position: absolute;
    right: 0;
    bottom: -1px;
    left: 0;
    height: 1px;
    background: var(--border-faint);
  }

  :global(.connector) {
    position: absolute;
    bottom: -11px;
    contain: layout paint;
  }

  :global(.connector.start) {
    left: -10.5px;
  }

  :global(.connector.end) {
    right: -10.5px;
  }

  .spacer {
    height: var(--header-height);
  }

  .brand {
    display: flex;
    min-height: 44px;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
    margin-right: 8px;
    border-radius: 8px;
    padding-inline: 4px;
  }

  .brand-name {
    display: none;
  }

  .link,
  .actions :global(.avatar) {
    display: inline-flex;
    min-height: 44px;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    padding-inline: 10px;
    color: var(--ink-alpha-64);
    transition:
      color 0.15s,
      background-color 0.15s,
      scale 0.1s;
  }

  .link:hover,
  .link[aria-current="page"],
  .actions :global(.avatar:hover) {
    background: var(--ink-alpha-4);
    color: var(--ink);
  }

  .link:active,
  .actions :global(.avatar:active) {
    background: var(--ink-alpha-7);
    scale: 0.98;
  }

  .actions {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: auto;
  }

  .actions :global(.avatar) {
    width: 44px;
    padding: 0;
    border: 1px solid var(--border-muted);
    background: var(--surface);
    color: var(--ink);
  }

  :global(.menu) {
    z-index: 110;
    min-width: 224px;
    padding: 6px;
    border: 1px solid var(--border-faint);
    border-radius: 12px;
    background: var(--surface);
    box-shadow: var(--menu-shadow);
    animation: menu-in 0.3s var(--ease-panel);
  }

  :global(.menu-email) {
    overflow: hidden;
    padding: 8px 10px;
    color: var(--ink-alpha-64);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  :global(.menu-item) {
    display: flex;
    min-height: 44px;
    cursor: default;
    align-items: center;
    border-radius: 8px;
    padding: 12px 10px 12px 14px;
    outline: none;
    transition: background-color 0.15s;
  }

  :global(.menu-item[data-highlighted]) {
    background: var(--ink-alpha-4);
  }

  @keyframes menu-in {
    from {
      opacity: 0;
      transform: translateY(-8px);
    }
  }

  @media (max-width: 639px) {
    .bar {
      padding-inline: 8px;
    }

    /* The icon alone is 24px wide. Padding and an equal negative margin widen the hit area to
       44px without moving the icon or the link beside it. */
    .brand {
      margin-inline: -16px -4px;
      padding-inline: 16px 4px;
    }

    .link {
      padding-inline: 8px;
    }

    .actions {
      gap: 4px;
    }
  }

  @media (min-width: 640px) {
    .brand-name {
      display: inline;
    }
  }

  @media (min-width: 768px) {
    .brand {
      min-height: 32px;
    }

    .link,
    .actions :global(.avatar) {
      min-height: 32px;
    }

    .actions :global(.avatar) {
      width: 32px;
    }

    :global(.menu-item) {
      min-height: 36px;
    }
  }

  @media (min-width: 996px) {
    .bar {
      padding-inline: 56px;
    }
  }
</style>
