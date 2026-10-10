<script lang="ts">
  /** The perimeter of a 4 x 4 grid in spinner pixels, clockwise from the top left. */
  const dots = [
    [3, 3],
    [7, 3],
    [11, 3],
    [15, 3],
    [15, 7],
    [15, 11],
    [15, 15],
    [11, 15],
    [7, 15],
    [3, 15],
    [3, 11],
    [3, 7],
  ];

  const isCorner = ([x, y]: number[]) => (x === 3 || x === 15) && (y === 3 || y === 15);
</script>

<span class="spinner" aria-hidden="true">
  {#each dots as dot (dot.join())}
    <span class="dot" data-corner={isCorner(dot) ? "" : undefined} style:left="{dot[0]}px" style:top="{dot[1]}px"
    ></span>
  {/each}
</span>

<style>
  .spinner {
    position: relative;
    display: block;
    width: 20px;
    height: 20px;
    min-width: 20px;
  }

  .dot {
    position: absolute;
    width: 2px;
    height: 2px;
    background: var(--heat-100);
    animation: flash 0.78s linear infinite;
  }

  .dot[data-corner] {
    animation-delay: 0.12s;
  }

  @keyframes flash {
    0% {
      opacity: 1;
    }

    15% {
      opacity: 0.4;
    }

    27% {
      opacity: 0.12;
    }

    38% {
      opacity: 0.04;
    }

    50%,
    100% {
      opacity: 0;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .dot {
      animation: none;
      opacity: 0.4;
    }
  }
</style>
