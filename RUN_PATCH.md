# Run page patch

Two small additions to core templates give the Judge plugin a top-nav link and a
per-pilot mirror of manually-entered laps on the **Run** page. RotorHazard's
plugin API doesn't (yet) expose a hook for injecting HTML into core templates, so
these are applied by hand. See `run_patch/run_page.html` for the exact snippets.

## 1. Nav link (`src/server/templates/layout.html`)

Add a **Judge** item right after **Run** in `<nav id="nav-main">`:

```html
<li class="admin-hide"><a href="/judge">{{ __("Judge") }}</a></li>
```

## 2. Per-node judge laps on the Run page (`src/server/templates/run.html`)

Inside the `{% for node in nodes %}` loop, immediately **after** the per-node
current-laps table (`<table class="laps" id="current_laps_{{ node.index }}">`),
add the mirror container:

```html
<!-- Judge plugin: laps added manually from the Judge page -->
<div class="judge-laps-panel" id="judge-laps-{{ node.index }}" data-node="{{ node.index }}"></div>
```

Then load the mirror script once anywhere in the run.html body:

```html
<script type="text/javascript" src="/judge/run_laps.js?{{ serverInfo['release_version'] | urlencode }}"></script>
```

Restart the server.

## Result

- A **Judge** link appears in the top menu (right of Run) → opens `/judge`.
- Under each pilot's node block (channel / RSSI graph / callsign / auto laps),
  an amber **Judge laps** panel lists the laps a judge entered from the `/judge`
  pages for the current race session (lap #, timestamp, lap time). The panel is
  hidden for nodes with no manual laps. It's served from `static/run_laps.js`,
  which polls `/judge/api/laps/<node_index>` (REST only, no socket dependency).
