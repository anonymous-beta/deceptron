#!/bin/bash
set -e

python3 banner.py 2>/dev/null || true

command -v python3 >/dev/null 2>&1 || { echo "[!] python3 required"; exit 1; }
command -v pip3   >/dev/null 2>&1 || { echo "[!] pip3 required"; exit 1; }

mkdir -p templates db generated

pip3 install -r requirements.txt --user 2>/dev/null || pip3 install -r requirements.txt

if [ ! -f config.json ]; then
    TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
    cat > config.json << EOF
{
    "ftp_host": "",
    "ftp_user": "",
    "ftp_pass": "",
    "ftp_path": "/public_html",
    "base_url": "",
    "server_host": "0.0.0.0",
    "server_port": 5000,
    "collector_url": "",
    "dashboard_token": "$TOKEN",
    "trust_proxy": false,
    "rate_limit": 60,
    "map_tile_url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "db_path": "db/hits.db"
}
EOF
    echo "[!] config.json created. Dashboard token: $TOKEN"
    echo "[!] Append ?token=<token> to dashboard URL, or set dashboard_token=\"\" to disable auth."
fi

python3 init_db.py
chmod +x deceptron.sh
echo "[+] Setup complete. Run: ./deceptron.sh server"