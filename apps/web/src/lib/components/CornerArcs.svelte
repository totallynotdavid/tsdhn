<script lang="ts">
  const path =
    "M11 1L11 11L10 11L10 7C10 3.68629 7.31371 1 4 1L-4.37114e-08 1L0 -4.80825e-07L11 4.37114e-07L11 1Z";
  const corners = ["top-start", "top-end", "bottom-start", "bottom-end"];
</script>

<!-- Rounded inner corners for a box that sits between the page rails. -->
<div class="arcs" aria-hidden="true">
  {#each corners as corner (corner)}
    <svg class="arc {corner}" fill="none" height="11" viewBox="0 0 11 11" width="11">
      <path d={path} fill="var(--border-faint)" />
    </svg>
  {/each}
</div>

<style>
  .arcs {
    position: absolute;
    inset: 0;
    pointer-events: none;
    contain: layout paint;
  }

  .arc {
    position: absolute;
  }

  .top-start {
    top: 0;
    left: 0;
    transform: rotate(-90deg);
  }

  .top-end {
    top: 0;
    right: 0;
  }

  .bottom-start {
    bottom: 0;
    left: 0;
    transform: rotate(180deg);
  }

  .bottom-end {
    right: 0;
    bottom: 0;
    transform: rotate(90deg);
  }
</style>
