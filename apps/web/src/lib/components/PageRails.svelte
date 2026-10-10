<!-- Viewport-tall hairlines fixed at the content column's edges while the page scrolls. -->
<div class="rails" aria-hidden="true"></div>

<style>
  .rails {
    position: fixed;
    top: 0;
    left: calc(50% - min(var(--container-width), 100% - 32px) / 2);
    z-index: 2;
    width: calc(100% - 32px);
    max-width: var(--container-width);
    height: 100vh;
    border-inline: 1px solid var(--border-faint);
    pointer-events: none;
  }
</style>
