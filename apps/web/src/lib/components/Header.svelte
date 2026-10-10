<script lang="ts">
  import { goto, invalidateAll } from "$app/navigation";
  import { page } from "$app/state";
  import { DropdownMenu } from "bits-ui";

  import favicon from "#lib/assets/favicon.svg";
  import { authClient } from "#lib/auth-client.js";
  import Button from "#lib/components/ui/Button.svelte";

  let { user }: { user: { name: string; email: string } } = $props();

  const onList = $derived(page.url.pathname.startsWith("/simulations"));
  const onNew = $derived(page.url.pathname === "/new");
  const initial = $derived((user.name || user.email).trim().charAt(0).toUpperCase());

  async function signOut() {
    await authClient.signOut();
    await invalidateAll();
    await goto("/login");
  }
</script>

<header class="border-line bg-surface border-b">
  <nav class="mx-auto flex h-14 max-w-6xl items-center gap-1 px-4 sm:px-6" aria-label="Principal">
    <a href="/" class="mr-3 flex items-center gap-2 font-semibold" aria-label="TSDHN, inicio">
      <img src={favicon} alt="" class="size-6" />
      <span class="hidden sm:inline">TSDHN</span>
    </a>
    <a
      href="/simulations"
      aria-current={onList ? "page" : undefined}
      class="flex min-h-11 items-center rounded-md px-3 text-sm md:min-h-9 {onList
        ? 'text-ink font-medium'
        : 'text-muted hover:text-ink'}"
    >
      Simulaciones
    </a>

    <div class="ml-auto flex items-center gap-2">
      {#if !onNew}
        <Button href="/new">Nueva simulación</Button>
      {/if}
      <DropdownMenu.Root>
        <DropdownMenu.Trigger
          class="bg-line text-ink hover:bg-line-strong flex size-11 items-center justify-center rounded-full text-sm font-medium md:size-9"
          aria-label="Cuenta de {user.email}"
        >
          {initial}
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="end"
            sideOffset={6}
            class="border-line bg-surface z-50 min-w-56 rounded-lg border p-1 shadow-lg"
          >
            <p class="text-muted truncate px-3 py-2 text-xs">{user.email}</p>
            <DropdownMenu.Item
              onSelect={signOut}
              class="data-highlighted:bg-canvas flex min-h-11 cursor-default items-center rounded-md px-3 text-sm outline-none md:min-h-9"
            >
              Cerrar sesión
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </div>
  </nav>
</header>
