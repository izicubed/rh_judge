# Marshal page patch

To enable the **Crossings Timeline** chart and **All Judge Laps** table on the Marshal page, two small additions are needed in `src/server/templates/marshal.html`:

1. A `<style>` block + `<script>` block inside the page's existing `$(document).ready(...)` handler.
2. A `<div id="judge-panel">` markup block placed at the end of `<main class="page-marshal">`.

Both additions are bundled as a single patch in `marshal_patch/` of this repository.

> The patch is intentionally distributed separately because RotorHazard's plugin API doesn't (yet) expose a hook for injecting arbitrary HTML into core templates. If/when that lands, the patch can be applied automatically by the plugin's `initialize()` call.

## Applying

1. Open `src/server/templates/marshal.html`.
2. Apply the contents of `marshal_patch/marshal_patch.diff` (or copy the snippets in `marshal_patch/style+script.html` and `marshal_patch/panel.html` into the marked locations).
3. Restart the server.

You should now see the **Judge Manual Laps** panel appear on the Marshal page whenever a saved race is selected, with:

- a Crossings Timeline chart (green = Auto, blue = Judge crossings — hollow markers on a dashed lane, click to pin info)
- the **All Judge Laps** table with inline edit/delete
- a compact "Add Lap" row to add a manual judge lap directly to the saved race
