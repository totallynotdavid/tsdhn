<script lang="ts">
  import { renderAscii, type AsciiShape } from "#lib/ascii.js";

  let { shape, columns, rows }: { shape: AsciiShape; columns: number; rows: number } = $props();

  const text = $derived(renderAscii(shape, columns, rows));
</script>

<pre class="field" aria-hidden="true">{text}</pre>

<style>
  .field {
    margin: 0;
    color: var(--heat-100);
    font-family: var(--font-mono);
    font-size: 7.5px;
    line-height: 10px;
    letter-spacing: 0;
    white-space: pre;
    pointer-events: none;
    user-select: none;
  }
</style>
