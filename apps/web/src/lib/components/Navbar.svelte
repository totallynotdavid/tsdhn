<script lang="ts">
  import { goto, invalidateAll } from "$app/navigation";
  import { page } from "$app/state";
  import { authClient } from "$lib/auth-client";

  let { user }: { user: { name: string; email: string } } = $props();
  let signingOut = $state(false);

  const links = [
    { href: "/dashboard", label: "Mis simulaciones" },
    { href: "/new", label: "Nueva simulación" },
  ];

  async function signOut() {
    signingOut = true;
    await authClient.signOut();
    await invalidateAll();
    await goto("/login");
  }
</script>

<header class="border-b border-neutral-200 bg-white">
  <nav class="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
    <div class="flex items-center gap-8">
      <a href="/dashboard" class="flex items-center gap-2 font-bold text-neutral-900">
        <span class="text-xl">🌊</span> TSDHN
      </a>
      <div class="hidden items-center gap-1 md:flex">
        {#each links as link (link.href)}
          <a
            href={link.href}
            class="rounded-md px-3 py-2 text-sm font-medium transition {page.url.pathname ===
            link.href
              ? 'bg-brand-50 text-brand-700'
              : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900'}"
          >
            {link.label}
          </a>
        {/each}
      </div>
    </div>

    <div class="flex items-center gap-3">
      <span class="hidden text-sm text-neutral-500 sm:inline">{user.email}</span>
      <button
        onclick={signOut}
        disabled={signingOut}
        class="rounded-md px-3 py-2 text-sm font-medium text-neutral-600 hover:bg-neutral-100 disabled:opacity-50"
      >
        Salir
      </button>
    </div>
  </nav>
</header>
