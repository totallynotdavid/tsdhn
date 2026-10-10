<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    label,
    hint,
    error,
    children,
  }: {
    label: string;
    hint?: string;
    error?: string | string[] | null;
    /** Receives the attributes that tie the input to its label, hint and error. */
    children: Snippet<[{ id: string; "aria-describedby": string | undefined; "aria-invalid": boolean }]>;
  } = $props();

  const id = $props.id();
  const message = $derived(Array.isArray(error) ? error[0] : error);
  // Expose the error instead of the hint so the input has one focused description.
  const describedBy = $derived(message ? `${id}-error` : hint ? `${id}-hint` : undefined);
</script>

<div class="field">
  <label for={id} class="t-label-md">{label}</label>
  {@render children({ id, "aria-describedby": describedBy, "aria-invalid": !!message })}
  {#if message}
    <p id="{id}-error" class="t-body-sm error">{message}</p>
  {:else if hint}
    <p id="{id}-hint" class="t-body-sm hint">{hint}</p>
  {/if}
</div>

<style>
  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  label {
    display: block;
    color: var(--ink);
  }

  .error {
    color: var(--danger);
  }

  .hint {
    color: var(--ink-alpha-64);
  }
</style>
