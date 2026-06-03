# How to apply the marshal page patch

Open `src/server/templates/marshal.html`.

## Step 1 — paste `style+script.html`

Find the end of the existing `{% block head %}` section. There is already a `<script type="text/javascript">$(document).ready(function () { ... });</script>` block near the end of the head block. **After** that closing `</script>`, paste the entire contents of [`style+script.html`](style+script.html).

There should be one combined `<style>…</style>` block followed by one `<script type="text/javascript">$(document).ready(function () { … });</script>` block.

## Step 2 — paste `panel.html`

Find the `<main class="page-marshal">` element and locate its closing `</main>`. Just before `</main>`, paste the contents of [`panel.html`](panel.html). It contains:

```html
<!-- Judge Plugin: manual lap comparison panel -->
<div id="judge-panel" class="panel" style="display:none"> ... </div>

<!-- Edit modal for an existing judge lap -->
<div id="judge-edit-modal"> ... </div>
```

## Step 3 — restart the server

That's it. After restarting, the Marshal page will show the **Judge Manual Laps** panel whenever a saved race is selected, with the Crossings Timeline chart, the All Judge Laps table (inline edit/delete), and the compact Add Lap row.

---

If you'd rather apply the change as a diff, see `marshal_patch.diff` — but expect it to drift as your local marshal.html changes. The snippet files above are the canonical reference.
