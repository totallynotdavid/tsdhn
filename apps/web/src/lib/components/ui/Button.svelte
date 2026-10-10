<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLAnchorAttributes, HTMLButtonAttributes } from "svelte/elements";

  type Variant = "primary" | "secondary" | "ghost";

  type Props = { variant?: Variant; class?: string; children: Snippet } & (
    | ({ href: string } & HTMLAnchorAttributes)
    | ({ href?: undefined } & HTMLButtonAttributes)
  );

  let { variant = "primary", class: klass = "", children, ...rest }: Props = $props();

  const base =
    "inline-flex min-h-11 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium whitespace-nowrap transition-colors md:min-h-9 disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50";
  const variants: Record<Variant, string> = {
    primary: "bg-accent text-white hover:bg-accent-strong",
    secondary: "border border-line-strong bg-surface text-ink hover:bg-canvas",
    ghost: "text-muted hover:bg-line/60 hover:text-ink",
  };
  const classes = $derived(`${base} ${variants[variant]} ${klass}`);
</script>

{#if rest.href !== undefined}
  <a class={classes} {...rest as HTMLAnchorAttributes}>{@render children()}</a>
{:else}
  <button class={classes} {...rest as HTMLButtonAttributes}>{@render children()}</button>
{/if}
