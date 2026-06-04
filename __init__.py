'''
Judge Plugin — manual lap entry for judges.

Summary page: /judge
Shows one card per pilot in the current heat (a shared timer plus an
ADD LAP button and lap history for each seat) so a single judge can mark
laps for every pilot from one screen, plus links to the per-node pages.
Pressing the keyboard digit for a seat (1–8) adds a lap to that pilot.
(Replaces the old /run/all, which now redirects here.)

Per-node pages: /judge/1 … /judge/8  (also /run/1 … /run/8)
Each page shows a race timer, an ADD LAP button, and a lap history table.

After a race is saved the laps appear on the Marshal page alongside the
automatic timing data.
'''

import logging
import os
import sqlite3
import time
import uuid

from flask import Blueprint, jsonify, make_response, redirect, render_template, request, send_file
from eventmanager import Evt

logger = logging.getLogger(__name__)

PLUGIN_DIR = os.path.dirname(os.path.realpath(__file__))
DB_PATH = os.path.join(PLUGIN_DIR, 'judge_laps.db')
MAX_NODES = 8


def initialize(rhapi):
    plugin = JudgePlugin(rhapi)
    plugin.setup()


class JudgePlugin:
    def __init__(self, rhapi):
        self._rhapi = rhapi
        self._session_id = None       # UUID for the current race session
        self._race_active = False     # True only while race_status == RACING
        self._session_locked = False  # True after LAPS_SAVE — read-only on /run/N

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup(self):
        self._init_db()

        self._rhapi.events.on(Evt.RACE_START,    self._on_race_start)
        self._rhapi.events.on(Evt.RACE_STOP,     self._on_race_stop)
        self._rhapi.events.on(Evt.RACE_FINISH,   self._on_race_stop)
        self._rhapi.events.on(Evt.LAPS_SAVE,     self._on_laps_save)
        self._rhapi.events.on(Evt.LAPS_DISCARD,  self._on_laps_discard)
        self._rhapi.events.on(Evt.LAPS_CLEAR,    self._on_laps_clear)

        bp = Blueprint('judge_plugin', __name__, template_folder='templates')
        self._register_routes(bp)
        self._rhapi.ui.blueprint_add(bp)

        self._register_settings_panel()
        logger.info('Judge plugin initialised. DB: %s', DB_PATH)

    # ------------------------------------------------------------------
    # DB bootstrap
    # ------------------------------------------------------------------

    def _init_db(self):
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS judge_lap (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id     TEXT    NOT NULL,
                    node_index     INTEGER NOT NULL,
                    lap_time_stamp REAL    NOT NULL,
                    lap_time       REAL    NOT NULL,
                    created_at     REAL    NOT NULL,
                    deleted        INTEGER NOT NULL DEFAULT 0,
                    saved_race_id  INTEGER
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_jl_session ON judge_lap(session_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_jl_race    ON judge_lap(saved_race_id)')
            conn.commit()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_race_start(self, args):
        self._session_id     = str(uuid.uuid4())
        self._race_active    = True
        self._session_locked = False
        logger.info('Judge plugin: new race session %s', self._session_id)

    def _on_race_stop(self, args):
        self._race_active = False

    def _on_laps_save(self, args):
        race_id = args.get('race_id')
        if race_id and self._session_id:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    'UPDATE judge_lap SET saved_race_id=? WHERE session_id=?',
                    (race_id, self._session_id),
                )
                conn.commit()
            logger.info('Judge plugin: session %s linked to race %s', self._session_id, race_id)
        # After save, the run session is read-only on /run/N
        self._session_locked = True

    def _on_laps_discard(self, args):
        if self._session_id:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute('DELETE FROM judge_lap WHERE session_id=?', (self._session_id,))
                conn.commit()
        self._session_id     = None
        self._race_active    = False
        self._session_locked = False

    def _on_laps_clear(self, args):
        # Save+Clear or any other clear path → wipe the active session
        self._session_id     = None
        self._race_active    = False
        self._session_locked = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _pilot_name(self, node_index):
        try:
            rc = self._rhapi._racecontext
            pilot_id = rc.race.node_pilots.get(node_index)
            if pilot_id:
                pilot = rc.rhdata.get_pilot(pilot_id)
                if pilot:
                    return pilot.callsign or pilot.name
        except Exception:
            pass
        return None

    def _num_seats(self):
        '''Number of available seats/nodes (clamped to MAX_NODES).'''
        try:
            n = len(self._rhapi._racecontext.interface.nodes)
            if n > 0:
                return min(n, MAX_NODES)
        except Exception:
            pass
        return MAX_NODES

    def _db_stats(self):
        '''Return dict with total/saved/unsaved lap counts.'''
        try:
            with sqlite3.connect(DB_PATH) as conn:
                total   = conn.execute('SELECT COUNT(*) FROM judge_lap WHERE deleted=0').fetchone()[0]
                saved   = conn.execute('SELECT COUNT(*) FROM judge_lap WHERE deleted=0 AND saved_race_id IS NOT NULL').fetchone()[0]
                return {'total': total, 'saved': saved, 'unsaved': total - saved}
        except Exception:
            return {'total': 0, 'saved': 0, 'unsaved': 0}

    def _clear_database(self, args):
        with sqlite3.connect(DB_PATH) as conn:
            deleted = conn.execute('SELECT COUNT(*) FROM judge_lap').fetchone()[0]
            conn.execute('DELETE FROM judge_lap')
            conn.commit()
        self._session_id  = None
        self._race_active = False
        logger.info('Judge plugin: database cleared (%d rows removed)', deleted)
        self._rhapi.ui.message_notify('Judge DB cleared ({} laps removed)'.format(deleted))

    def _register_settings_panel(self):
        stats = self._db_stats()
        self._rhapi.ui.register_panel(
            'judge_db',
            'Judge — Database',
            'settings',
            order=0,
            open=True,
        )
        self._rhapi.ui.register_markdown(
            'judge_db',
            'judge_db_info',
            (
                'Manual judge laps are stored in a separate SQLite file:\n\n'
                '`{path}`\n\n'
                '**Stats:** {total} laps total &nbsp;·&nbsp; '
                '{saved} linked to saved races &nbsp;·&nbsp; '
                '{unsaved} from unsaved sessions\n\n'
                '[⬇ &nbsp;Download backup](/judge/api/db/backup)'
            ).format(path=DB_PATH, **stats),
        )
        self._rhapi.ui.register_quickbutton(
            'judge_db',
            'judge_clear_db',
            'Clear All Judge Laps',
            self._clear_database,
            {},
        )

    def _prev_ts(self, conn, session_id, node_index, exclude_id=None, before_ts=None):
        '''Return the lap_time_stamp of the nearest preceding non-deleted lap.'''
        if exclude_id is not None and before_ts is not None:
            row = conn.execute(
                '''SELECT lap_time_stamp FROM judge_lap
                   WHERE session_id=? AND node_index=? AND deleted=0
                     AND id!=? AND lap_time_stamp<?
                   ORDER BY lap_time_stamp DESC LIMIT 1''',
                (session_id, node_index, exclude_id, before_ts),
            ).fetchone()
        else:
            row = conn.execute(
                '''SELECT lap_time_stamp FROM judge_lap
                   WHERE session_id=? AND node_index=? AND deleted=0
                   ORDER BY lap_time_stamp DESC LIMIT 1''',
                (session_id, node_index),
            ).fetchone()
        return row[0] if row else 0.0

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    def _register_routes(self, bp):
        plugin = self  # capture for closures

        # Plugin code changes regularly — keep browsers from serving stale HTML
        # that would emit socket calls with the wrong payload shape.
        def _nocache(html):
            resp = make_response(html)
            resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp.headers['Pragma']        = 'no-cache'
            resp.headers['Expires']       = '0'
            return resp

        def _render_all():
            return _nocache(render_template('judge_run_all.html', max_nodes=MAX_NODES))

        def _render_node(node_num):
            if not 1 <= node_num <= MAX_NODES:
                return 'Node number must be 1–8', 404
            return _nocache(render_template('judge_run.html',
                                            node_num=node_num,
                                            node_index=node_num - 1))

        # ── Judge summary page (all pilots in heat) — /judge ──────────
        @bp.route('/judge')
        def judge_all():
            return _render_all()

        # ── Per-node judge pages — /judge/1 … /judge/8 ────────────────
        @bp.route('/judge/<int:node_num>')
        def judge_node(node_num):
            return _render_node(node_num)

        # ── Back-compat: the summary page moved from /run/all to /judge
        @bp.route('/run/all')
        def judge_page_all():
            return redirect('/judge', code=302)

        # ── Back-compat: per-node pages still available at /run/1 … /run/8
        @bp.route('/run/<int:node_num>')
        def judge_page(node_num):
            return _render_node(node_num)

        # ── Race / session status ─────────────────────────────────────
        @bp.route('/judge/api/status')
        def api_status():
            rc = plugin._rhapi._racecontext
            pilot_names = {}
            for i in range(MAX_NODES):
                name = plugin._pilot_name(i)
                if name:
                    pilot_names[str(i)] = name
            return jsonify({
                'race_active':  plugin._race_active,
                'race_status':  rc.race.race_status,
                'session_id':   plugin._session_id,
                'locked':       plugin._session_locked,
                'pilot_names':  pilot_names,
                'num_seats':    plugin._num_seats(),
            })

        # ── Laps for current session ───────────────────────────────────
        @bp.route('/judge/api/laps/<int:node_index>')
        def api_get_laps(node_index):
            if not plugin._session_id:
                return jsonify([])
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    '''SELECT * FROM judge_lap
                       WHERE session_id=? AND node_index=? AND deleted=0
                       ORDER BY lap_time_stamp''',
                    (plugin._session_id, node_index),
                ).fetchall()
            return jsonify([dict(r) for r in rows])

        @bp.route('/judge/api/laps/<int:node_index>', methods=['POST'])
        def api_add_lap(node_index):
            if not plugin._session_id:
                return jsonify({'error': 'No active race'}), 400
            if plugin._session_locked:
                return jsonify({'error': 'Race is saved — laps are read-only'}), 403
            data = request.get_json(silent=True) or {}
            ts = float(data.get('lap_time_stamp', 0))
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                prev_ts = plugin._prev_ts(conn, plugin._session_id, node_index)
                lap_time = ts - prev_ts
                cur = conn.execute(
                    '''INSERT INTO judge_lap
                       (session_id, node_index, lap_time_stamp, lap_time, created_at)
                       VALUES (?,?,?,?,?)''',
                    (plugin._session_id, node_index, ts, lap_time, time.time()),
                )
                conn.commit()
                row = conn.execute('SELECT * FROM judge_lap WHERE id=?', (cur.lastrowid,)).fetchone()
            return jsonify(dict(row)), 201

        # ── Single lap operations ──────────────────────────────────────
        def _lap_is_locked(conn, lap_id):
            '''A lap is locked from /run/N if it has no saved_race_id (active session)
               AND the current session is locked. Saved laps are editable from Marshal.'''
            row = conn.execute(
                'SELECT session_id, saved_race_id FROM judge_lap WHERE id=?', (lap_id,)
            ).fetchone()
            if not row:
                return False, None
            return (
                row['saved_race_id'] is None
                and plugin._session_locked
                and row['session_id'] == plugin._session_id,
                row,
            )

        @bp.route('/judge/api/laps/entry/<int:lap_id>', methods=['DELETE'])
        def api_delete_lap(lap_id):
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                locked, _ = _lap_is_locked(conn, lap_id)
                if locked:
                    return jsonify({'error': 'Race is saved — laps are read-only'}), 403
                conn.execute('UPDATE judge_lap SET deleted=1 WHERE id=?', (lap_id,))
                conn.commit()
            return jsonify({'ok': True})

        @bp.route('/judge/api/laps/entry/<int:lap_id>', methods=['PUT'])
        def api_edit_lap(lap_id):
            data = request.get_json(silent=True) or {}
            new_ts = float(data.get('lap_time_stamp', 0))
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                locked, _ = _lap_is_locked(conn, lap_id)
                if locked:
                    return jsonify({'error': 'Race is saved — laps are read-only'}), 403
                meta = conn.execute(
                    'SELECT session_id, node_index FROM judge_lap WHERE id=?', (lap_id,)
                ).fetchone()
                if not meta:
                    return jsonify({'error': 'Not found'}), 404
                prev_ts = plugin._prev_ts(
                    conn, meta['session_id'], meta['node_index'],
                    exclude_id=lap_id, before_ts=new_ts,
                )
                conn.execute(
                    'UPDATE judge_lap SET lap_time_stamp=?, lap_time=? WHERE id=?',
                    (new_ts, new_ts - prev_ts, lap_id),
                )
                conn.commit()
                updated = conn.execute('SELECT * FROM judge_lap WHERE id=?', (lap_id,)).fetchone()
            return jsonify(dict(updated))

        # ── DB management ─────────────────────────────────────────────
        @bp.route('/judge/api/db/backup')
        def api_db_backup():
            return send_file(
                DB_PATH,
                as_attachment=True,
                download_name='judge_laps.db',
                mimetype='application/octet-stream',
            )

        # ── Marshal view: laps by saved race id ───────────────────────
        @bp.route('/judge/api/marshal/<int:race_id>')
        def api_marshal_laps(race_id):
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    '''SELECT * FROM judge_lap
                       WHERE saved_race_id=? AND deleted=0
                       ORDER BY node_index, lap_time_stamp''',
                    (race_id,),
                ).fetchall()
            result = {}
            for r in rows:
                key = str(r['node_index'])
                result.setdefault(key, []).append(dict(r))
            return jsonify(result)

        # ── Marshal: add a judge lap directly to a saved race ─────────
        @bp.route('/judge/api/marshal/<int:race_id>/<int:node_index>', methods=['POST'])
        def api_marshal_add_lap(race_id, node_index):
            data = request.get_json(silent=True) or {}
            ts = float(data.get('lap_time_stamp', 0))
            if ts < 0:
                return jsonify({'error': 'lap_time_stamp must be >= 0'}), 400
            # Synthetic session id so this lap is grouped with other marshal-added entries
            session_id = 'marshal-race-{}'.format(race_id)
            with sqlite3.connect(DB_PATH) as conn:
                conn.row_factory = sqlite3.Row
                # lap_time = gap from the nearest preceding non-deleted lap on the same race+node
                prev = conn.execute(
                    '''SELECT lap_time_stamp FROM judge_lap
                       WHERE saved_race_id=? AND node_index=? AND deleted=0
                         AND lap_time_stamp < ?
                       ORDER BY lap_time_stamp DESC LIMIT 1''',
                    (race_id, node_index, ts),
                ).fetchone()
                prev_ts = prev['lap_time_stamp'] if prev else 0.0
                lap_time = ts - prev_ts
                cur = conn.execute(
                    '''INSERT INTO judge_lap
                       (session_id, node_index, lap_time_stamp, lap_time, created_at, saved_race_id)
                       VALUES (?,?,?,?,?,?)''',
                    (session_id, node_index, ts, lap_time, time.time(), race_id),
                )
                new_id = cur.lastrowid
                # Fix lap_time of the next lap so the chain stays consistent
                nxt = conn.execute(
                    '''SELECT id, lap_time_stamp FROM judge_lap
                       WHERE saved_race_id=? AND node_index=? AND deleted=0
                         AND lap_time_stamp > ?
                       ORDER BY lap_time_stamp ASC LIMIT 1''',
                    (race_id, node_index, ts),
                ).fetchone()
                if nxt:
                    conn.execute(
                        'UPDATE judge_lap SET lap_time=? WHERE id=?',
                        (nxt['lap_time_stamp'] - ts, nxt['id']),
                    )
                conn.commit()
                row = conn.execute('SELECT * FROM judge_lap WHERE id=?', (new_id,)).fetchone()
            return jsonify(dict(row)), 201
