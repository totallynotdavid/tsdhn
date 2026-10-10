<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLAnchorAttributes, HTMLButtonAttributes } from "svelte/elements";

  type Variant = "primary" | "secondary" | "tertiary";

  type Props = { variant?: Variant; class?: string; children: Snippet } & (
    | ({ href: string } & HTMLAnchorAttributes)
    | ({ href?: undefined } & HTMLButtonAttributes)
  );

  let { variant = "primary", class: klass = "", children, ...rest }: Props = $props();

  const classes = $derived(`button ${variant} t-label-md ${klass}`);
</script>

{#if rest.href !== undefined}
  <a class={classes} {...rest as HTMLAnchorAttributes}>
    {#if variant === "primary"}<span class="sheen" aria-hidden="true"></span>{/if}
    <span class="label">{@render children()}</span>
  </a>
{:else}
  <button class={classes} {...rest as HTMLButtonAttributes}>
    {#if variant === "primary"}<span class="sheen" aria-hidden="true"></span>{/if}
    <span class="label">{@render children()}</span>
  </button>
{/if}

<style>
  .button {
    position: relative;
    display: inline-flex;
    min-height: 44px;
    align-items: center;
    justify-content: center;
    padding: 8px 10px;
    border-radius: 10px;
    white-space: nowrap;
    transition:
      all 0.2s,
      scale 0.1s,
      box-shadow 0.1s;
  }

  .label {
    position: relative;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding-inline: 6px;
  }

  .button:active {
    transition:
      all 0.2s,
      scale 50ms,
      box-shadow 50ms;
    scale: 0.99;
  }

  .button:disabled,
  .button[aria-disabled="true"] {
    pointer-events: none;
    opacity: 0.5;
  }

  .primary {
    background: var(--button-primary-fill);
    box-shadow: var(--button-primary-shadow);
    color: #fff;
  }

  .primary:hover {
    box-shadow: var(--button-primary-shadow-hover);
  }

  .primary:active {
    box-shadow: var(--button-primary-shadow);
    scale: 0.995;
  }

  .secondary {
    background: var(--ink-alpha-4);
    color: var(--ink);
  }

  .secondary:hover {
    background: var(--ink-alpha-6);
  }

  .secondary:active {
    background: var(--ink-alpha-7);
  }

  .tertiary {
    color: var(--ink);
  }

  .tertiary:hover {
    background: var(--ink-alpha-4);
  }

  .tertiary:active {
    background: var(--ink-alpha-7);
  }

  .sheen {
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: linear-gradient(#fff, transparent);
    opacity: 0.06;
    pointer-events: none;
    transition: opacity 0.2s;
  }

  .button:hover .sheen {
    opacity: 0.08;
  }

  .button:active .sheen {
    opacity: 0;
    transition: opacity 50ms;
  }

  @media (min-width: 768px) {
    .button {
      min-height: 36px;
    }
  }
</style>
