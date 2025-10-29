import os
import time
import json
import sqlite3
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
import requests

# Config
APP_DIR = os.path.dirname(__file__)
BASE_DIR = os.path.dirname(APP_DIR)
WEBAPP_DIR = os.path.join(BASE_DIR, 'webapp')
DB_PATH = os.path.join(APP_DIR, 'data.db')
NODE_RED_BASE = os.environ.get('NODE_RED_BASE', 'http://127.0.0.1:1880')

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# --- SQLite helpers ---

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript(
        '''
        CREATE TABLE IF NOT EXISTS measurements (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts INTEGER NOT NULL,
          key TEXT NOT NULL,
          addr TEXT,
          value REAL,
          unit TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_measurements_key_ts ON measurements(key, ts);

        CREATE TABLE IF NOT EXISTS hysteresis_points (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts INTEGER NOT NULL,
          angle REAL,
          torque REAL
        );
        CREATE INDEX IF NOT EXISTS idx_hysteresis_ts ON hysteresis_points(ts);

        CREATE TABLE IF NOT EXISTS commands_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts INTEGER NOT NULL,
          cmd TEXT,
          addr TEXT,
          params TEXT,
          ok INTEGER
        );
        '''
    )
    db.commit()

# --- Utils ---

def now_ms():
    return int(time.time() * 1000)

def normalize_values(data):
    """Convert various upstream shapes to {key: {addr, value, unit}}"""
    values = {}
    if not data:
        return values
    if isinstance(data, dict) and 'values' in data and isinstance(data['values'], dict):
        # Already normalized
        return data['values']
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, dict):
                values[k] = {
                    'addr': v.get('addr'),
                    'value': v.get('value'),
                    'unit': v.get('unit')
                }
            else:
                # Plain numeric
                values[k] = {'addr': None, 'value': v, 'unit': None}
        return values
    if isinstance(data, list):
        # List of points
        for p in data:
            key = p.get('key') or p.get('name') or p.get('addr')
            if not key:
                continue
            values[key] = {'addr': p.get('addr'), 'value': p.get('value'), 'unit': p.get('unit')}
        return values
    return values

def save_measurements(values, ts):
    if not values:
        return 0
    db = get_db()
    rows = 0
    for k, meta in values.items():
        db.execute(
            'INSERT INTO measurements(ts, key, addr, value, unit) VALUES (?,?,?,?,?)',
            (ts, k, meta.get('addr'), meta.get('value'), meta.get('unit'))
        )
        rows += 1
    db.commit()
    return rows

def save_hysteresis(points, ts):
    if not points:
        return 0
    db = get_db()
    for p in points:
        db.execute(
            'INSERT INTO hysteresis_points(ts, angle, torque) VALUES (?,?,?)',
            (ts, float(p.get('angle', 0)), float(p.get('torque', 0)))
        )
    db.commit()
    return len(points)

# --- API ---

@app.route('/health')
def health():
    return jsonify({'ok': True, 'time': now_ms()})

@app.route('/api/ingest', methods=['POST'])
def ingest():
    init_db()
    payload = request.get_json(silent=True) or {}
    ts = int(payload.get('timestamp') or now_ms())
    values = normalize_values(payload.get('values') or payload)
    saved = save_measurements(values, ts)
    hyst = payload.get('hysteresis') or payload.get('points')
    hyst_saved = 0
    if isinstance(hyst, list):
        hyst_saved = save_hysteresis(hyst, ts)
    return jsonify({'ok': True, 'saved': saved, 'hysteresis_saved': hyst_saved})

@app.route('/api/get/datas', methods=['POST'])
def get_datas():
    init_db()
    payload = request.get_json(silent=True) or {}
    keys = payload.get('keys') or []
    try:
        # Proxy to Node-RED
        r = requests.post(f'{NODE_RED_BASE}/get/datas', json=payload, timeout=3)
        r.raise_for_status()
        data = r.json()
        ts = int(data.get('timestamp') or now_ms())
        values = normalize_values(data.get('values') or data)
        save_measurements(values, ts)
        return jsonify({'timestamp': ts, 'values': values})
    except Exception as e:
        # Fallback to DB
        db = get_db()
        out = {'timestamp': now_ms(), 'values': {}}
        for k in keys:
            row = db.execute(
                'SELECT value, unit, addr, ts FROM measurements WHERE key=? ORDER BY ts DESC LIMIT 1', (k,)
            ).fetchone()
            if row:
                out['values'][k] = {'value': row[0], 'unit': row[1], 'addr': row[2]}
                out['timestamp'] = row[3]
        return jsonify(out)

@app.route('/api/hysteresis', methods=['GET'])
def api_hysteresis():
    init_db()
    db = get_db()
    last_ts_row = db.execute('SELECT MAX(ts) AS ts FROM hysteresis_points').fetchone()
    ts = last_ts_row['ts'] if last_ts_row and last_ts_row['ts'] else None
    if not ts:
        # Provide mock points
        pts = make_mock_hysteresis()
        return jsonify({'hysteresis': pts})
    rows = db.execute('SELECT angle, torque FROM hysteresis_points WHERE ts=? ORDER BY id ASC', (ts,)).fetchall()
    pts = [{'angle': r['angle'], 'torque': r['torque'] } for r in rows]
    return jsonify({'hysteresis': pts})

@app.route('/api/set/data', methods=['POST'])
def set_data():
    init_db()
    payload = request.get_json(silent=True) or {}
    ok = 0
    try:
        r = requests.post(f'{NODE_RED_BASE}/set/data', json=payload, timeout=3)
        r.raise_for_status()
        resp = r.json() if r.headers.get('Content-Type','').startswith('application/json') else {'status': r.text}
        ok = 1
    except Exception as e:
        resp = {'error': str(e)}
    # Log command
    db = get_db()
    db.execute('INSERT INTO commands_log(ts, cmd, addr, params, ok) VALUES (?,?,?,?,?)', (
        now_ms(), str(payload.get('cmd')), str(payload.get('addr')), json.dumps(payload.get('params') or {}), ok
    ))
    db.commit()
    return jsonify({'ok': bool(ok), 'resp': resp})

# --- Mock hysteresis ---

def make_mock_hysteresis(count=240, T=10.0, backlash=0.6, k=0.8):
    pts = []
    for i in range(count):
        u = i/(count-1)
        half = (u < 0.5)
        t = (u*2*T - T) if half else ((u-0.5)*2*T - T)  # -T..+T..-T
        hysteresis_offset = (backlash/2.0 if t >= 0 else -backlash/2.0)
        angle = k*t + hysteresis_offset + 0.1*__import__('math').sin(4*u*__import__('math').pi)
        pts.append({'angle': angle, 'torque': t})
    return pts

@app.route('/')
def serve_index():
    return send_from_directory(WEBAPP_DIR, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    # If file exists under webapp, serve it; otherwise fallback to index for SPA routing
    try:
        return send_from_directory(WEBAPP_DIR, filename)
    except Exception:
        return send_from_directory(WEBAPP_DIR, 'index.html')


@app.route('/api/get/datas', methods=['POST'])
def get_datas():
    init_db()
    payload = request.get_json(silent=True) or {}
    keys = payload.get('keys') or []
    try:
        # Proxy to Node-RED
        r = requests.post(f'{NODE_RED_BASE}/get/datas', json=payload, timeout=3)
        r.raise_for_status()
        data = r.json()
        ts = int(data.get('timestamp') or now_ms())
        values = normalize_values(data.get('values') or data)
        save_measurements(values, ts)
        return jsonify({'timestamp': ts, 'values': values})
    except Exception as e:
        # Fallback to DB
        db = get_db()
        out = {'timestamp': now_ms(), 'values': {}}
        for k in keys:
            row = db.execute(
                'SELECT value, unit, addr, ts FROM measurements WHERE key=? ORDER BY ts DESC LIMIT 1', (k,)
            ).fetchone()
            if row:
                out['values'][k] = {'value': row[0], 'unit': row[1], 'addr': row[2]}
                out['timestamp'] = row[3]
        return jsonify(out)

@app.route('/api/hysteresis', methods=['GET'])
def api_hysteresis():
    init_db()
    db = get_db()
    last_ts_row = db.execute('SELECT MAX(ts) AS ts FROM hysteresis_points').fetchone()
    ts = last_ts_row['ts'] if last_ts_row and last_ts_row['ts'] else None
    if not ts:
        # Provide mock points
        pts = make_mock_hysteresis()
        return jsonify({'hysteresis': pts})
    rows = db.execute('SELECT angle, torque FROM hysteresis_points WHERE ts=? ORDER BY id ASC', (ts,)).fetchall()
    pts = [{'angle': r['angle'], 'torque': r['torque'] } for r in rows]
    return jsonify({'hysteresis': pts})

@app.route('/api/set/data', methods=['POST'])
def set_data():
    init_db()
    payload = request.get_json(silent=True) or {}
    ok = 0
    try:
        r = requests.post(f'{NODE_RED_BASE}/set/data', json=payload, timeout=3)
        r.raise_for_status()
        resp = r.json() if r.headers.get('Content-Type','').startswith('application/json') else {'status': r.text}
        ok = 1
    except Exception as e:
        resp = {'error': str(e)}
    # Log command
    db = get_db()
    db.execute('INSERT INTO commands_log(ts, cmd, addr, params, ok) VALUES (?,?,?,?,?)', (
        now_ms(), str(payload.get('cmd')), str(payload.get('addr')), json.dumps(payload.get('params') or {}), ok
    ))
    db.commit()
    return jsonify({'ok': bool(ok), 'resp': resp})

# --- Mock hysteresis ---

def make_mock_hysteresis(count=240, T=10.0, backlash=0.6, k=0.8):
    pts = []
    for i in range(count):
        u = i/(count-1)
        half = (u < 0.5)
        t = (u*2*T - T) if half else ((u-0.5)*2*T - T)  # -T..+T..-T
        hysteresis_offset = (backlash/2.0 if t >= 0 else -backlash/2.0)
        angle = k*t + hysteresis_offset + 0.1*__import__('math').sin(4*u*__import__('math').pi)
        pts.append({'angle': angle, 'torque': t})
    return pts

if __name__ == '__main__':
    # Ensure DB initialized
    with app.app_context():
        init_db()
    port = int(os.environ.get('PORT', '5000'))
    app.run(host='0.0.0.0', port=port, debug=True)