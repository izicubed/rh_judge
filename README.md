# rh_judge — RotorHazard Judge Plugin

Manual lap entry for race judges, with a comparison view on the Marshal page.

The plugin adds:

- per-node judge pages at `/run/1` … `/run/8` where a judge records laps with a single tap on the **Add Lap** button while the race is running
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
```

Then apply the **Marshal page patch** (see `MARSHAL_PATCH.md`) so the comparison UI shows up.
Restart the server.

### Option B — bundle into the source tree

Copy this folder to `src/server/bundled_plugins/rh_judge/` instead of `plugins/rh_judge/`. The plugin is auto-loaded at startup. Marshal patch is still required.

## Routes

| Method   | Path                                              | Purpose                              |
|----------|---------------------------------------------------|--------------------------------------|
| GET      | `/run/<N>`                                        | Judge page for node N (1–8)          |
| GET      | `/judge/api/status`                               | Race status + pilot names + lock     |
| GET      | `/judge/api/laps/<node_index>`                    | Current session laps                 |
| POST     | `/judge/api/laps/<node_index>`                    | Add lap (during active race)         |
| PUT      | `/judge/api/laps/entry/<id>`                      | Edit a lap                           |
| DELETE   | `/judge/api/laps/entry/<id>`                      | Soft-delete a lap                    |
| GET      | `/judge/api/marshal/<race_id>`                    | Saved laps grouped by node index     |
| POST     | `/judge/api/marshal/<race_id>/<node_index>`       | Add a manual lap to a saved race     |
| GET      | `/judge/api/db/backup`                            | Download the plugin's SQLite DB      |

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
