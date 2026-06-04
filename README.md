# rh_judge — RotorHazard Judge Plugin

Manual lap entry for race judges, with a comparison view on the Marshal page.

The plugin adds:

- a combined heat page at `/judge` showing one card per pilot in the current heat (shared timer, per-seat Add Lap + lap history), with keyboard shortcuts `1`–`8` to add a lap to the matching seat and links to each single page — so a single judge can mark laps for every pilot from one screen
- per-node judge pages at `/judge/1` … `/judge/8` (also `/run/1` … `/run/8`) where a judge records laps with a single tap on the **Add Lap** button while the race is running
- a **Judge** link in the top navigation (right of Run) that opens `/judge`
- a per-pilot **Judge laps** mirror on the Run page: under each node block (channel / RSSI graph / callsign / auto laps) an amber panel lists the laps a judge entered from the `/judge` pages for the current session
- a **Judge Manual Laps** panel on the Marshal page that visualises both automatic and manual crossings on a shared timeline
- inline edit/delete and "add manual lap" controls on the Marshal page (Marshal-side manual entry attaches the lap directly to a saved race)
- a Settings page panel for downloading or clearing the plugin's database

After "Save and Clear" on the `/run` page the judge pages automatically switch to read-only.

## Installation

### Option A — drop-in install (community plugin)

Copy the contents of this repository into RotorHazard's plugin directory so the tree looks like:

```
src/server/plugins/rh_judge/
    __init__.py
    manifest.json
    templates/
        judge_run.html
        judge_run_all.html
    static/
        run_laps.js
```

Then apply the patches to the core templates:

- **Marshal page patch** (see `MARSHAL_PATCH.md`) for the comparison UI.
- **Run page patch** (see `RUN_PATCH.md`) for the top-nav **Judge** link and the
  per-pilot judge-laps mirror on the Run page.

Restart the server.

### Option B — bundle into the source tree

Copy this folder to `src/server/bundled_plugins/rh_judge/` instead of `plugins/rh_judge/`. The plugin is auto-loaded at startup. Marshal patch is still required.

## Routes

| Method   | Path                                              | Purpose                              |
|----------|---------------------------------------------------|--------------------------------------|
| GET      | `/judge`                                          | Combined heat page (all pilots) + links to single pages |
| GET      | `/judge/<N>`                                       | Per-node judge page (1–8); also `/run/<N>` |
| GET      | `/run/all`                                         | Redirects to `/judge` (back-compat)  |
| GET      | `/judge/api/status`                               | Race status + pilot names + lock + seat count |
| GET      | `/judge/api/laps/<node_index>`                    | Current session laps                 |
| POST     | `/judge/api/laps/<node_index>`                    | Add lap (during active race)         |
| PUT      | `/judge/api/laps/entry/<id>`                      | Edit a lap                           |
| DELETE   | `/judge/api/laps/entry/<id>`                      | Soft-delete a lap                    |
| GET      | `/judge/api/marshal/<race_id>`                    | Saved laps grouped by node index     |
| POST     | `/judge/api/marshal/<race_id>/<node_index>`       | Add a manual lap to a saved race     |
| GET      | `/judge/api/db/backup`                            | Download the plugin's SQLite DB      |

## Combined heat page (`/judge`)

One screen for the whole heat (the old `/run/all` now redirects here). It uses the same Socket.IO time-sync and `race_status` handling as the per-node pages, but a single shared timer drives every card.

- On connect (and every few seconds) it reads `/judge/api/status` and renders one card per node that has a pilot assigned. If none are assigned (e.g. mock/dev), it falls back to all available seats (`num_seats`).
- Each card has its own **Add Lap** button, lap count and a scrollable lap history with the same edit/delete controls as the single-node page. Laps are written through the same `/judge/api/laps/<node_index>` endpoints, so they are identical to laps added from a single page.
- **Keyboard:** pressing a digit `1`–`8` (top row or numpad) adds a lap to the seat with that number while the race is `RACING`. Keys are ignored while the edit modal is open or a field is focused.
- **Single-page links:** a "Single pages" nav row (`/judge/1` … `/judge/8`) and an ↗ link on each card open the per-node pages; each single page's `◈ Judge` logo links back to `/judge`.
- The grid is rebuilt only when the set of seats changes (heat change); otherwise it just refreshes pilot names and lock state, so in-progress laps are not disturbed.

## Data Storage

The plugin keeps its data in `judge_laps.db` next to the plugin (its own SQLite file — does not touch RotorHazard's main database).

Schema:

| Column          | Type      | Notes                                   |
|-----------------|-----------|-----------------------------------------|
| id              | INTEGER   | Auto-increment primary key              |
| session_id      | TEXT      | UUID per race session                   |
| node_index      | INTEGER   | 0-based                                 |
| lap_time_stamp  | REAL      | ms from race start                      |
| lap_time        | REAL      | ms since previous judge lap on the node |
| created_at      | REAL      | Unix epoch when added                   |
| deleted         | INTEGER   | Soft-delete flag                        |
| saved_race_id   | INTEGER   | FK to `SavedRaceMeta.id` after save     |

## Race session flow

1. `RACE_START` → new `session_id` generated, `_race_active = True`.
2. Judge adds laps from `/run/N` → stored with that `session_id`, `saved_race_id = NULL`.
3. `LAPS_SAVE` → `saved_race_id` is set for the session's laps, session is locked.
4. `LAPS_DISCARD` / `LAPS_CLEAR` → laps removed, session reset, lock cleared.
5. `RACE_STOP` / `RACE_FINISH` → `_race_active = False` (laps preserved).

## License

MIT — see `LICENSE`.
