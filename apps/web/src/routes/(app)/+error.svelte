<script lang="ts">
  import { page } from "$app/state";

  import ErrorState from "#lib/components/ErrorState.svelte";
</script>

<ErrorState status={page.status} message={page.error?.message} />
