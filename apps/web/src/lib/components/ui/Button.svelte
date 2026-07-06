<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLButtonAttributes } from "svelte/elements";

  type Variant = "primary" | "outline" | "ghost" | "danger";

  let {
    variant = "primary",
    class: klass = "",
    children,
    ...rest
  }: { variant?: Variant; class?: string; children: Snippet } & HTMLButtonAttributes =
    $props();

  const base =
    "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 disabled:pointer-events-none disabled:opacity-50";
  const variants: Record<Variant, string> = {
    primary: "bg-brand-600 text-white hover:bg-brand-700",
    outline: "border border-neutral-300 bg-white text-neutral-800 hover:bg-neutral-50",
    ghost: "text-neutral-700 hover:bg-neutral-100",
    danger: "bg-red-600 text-white hover:bg-red-700",
  };
</script>

<button class="{base} {variants[variant]} {klass}" {...rest}>
  {@render children()}
</button>
