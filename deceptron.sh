#!/bin/bash
# DECEPTRON v1.2 Main CLI
VERSION="1.2"
PID_FILE=".deceptron.pid"

banner() { python3 banner.py 2>/dev/null || echo "  DECEPTRON v$VERSION"; }

help_menu() {
    banner
    cat <<USAGE
Usage: ./deceptron.sh <command>

Commands:
  setup       — Initialize environment and database
  server      — Start collector + dashboard (foreground)
  server -b   — Start server in background
  stop        — Stop background server
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
    if [ "$2" = "-b" ] || [ "$2" = "--background" ]; then
        nohup python3 server.py > server.log 2>&1 &
        echo $! > "$PID_FILE"
        echo "[+] Server started in background (PID: $(cat $PID_FILE))"
        echo "[+] Logs: tail -f server.log"
    else
        echo "[+] Starting server... (Ctrl+C to stop)"
        python3 server.py
    fi
}

cmd_stop() {
    if [ -f "$PID_FILE" ] && ps -p "$(cat $PID_FILE)" >/dev/null 2>&1; then
        kill "$(cat $PID_FILE)" && rm -f "$PID_FILE" && echo "[+] Server stopped"
    else
        echo "[!] Server not running"
        rm -f "$PID_FILE"
    fi
}

cmd_generate() { python3 generate.py; }

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
    { command -v xdg-open >/dev/null && xdg-open http://localhost:5000; } \
    || { command -v termux-open >/dev/null && termux-open http://localhost:5000; } || true
}

cmd_export() {
    fmt=${2:-json}
    case "$fmt" in json|csv) ;; *) echo "[!] Format must be json or csv"; exit 1 ;; esac
    python3 - "$fmt" <<'PYEOF'
import sqlite3, json, csv, sys
from init_db import init_db
fmt = sys.argv[1]
conn = sqlite3.connect(init_db())
c = conn.cursor()
c.execute("SELECT * FROM hits ORDER BY timestamp DESC")
rows = c.fetchall()
cols = [d[0] for d in c.description]
conn.close()
out = f"export.{fmt}"
with open(out, "w", newline="") as f:
    if fmt == "json":
        json.dump([dict(zip(cols, r)) for r in rows], f, indent=2)
    else:
        w = csv.writer(f); w.writerow(cols); w.writerows(rows)
print(f"[+] Exported: {out}")
PYEOF
}

cmd_shorten() {
    url=$2
    [ -z "$url" ] && read -r -p "[?] URL to shorten: " url
    # FIX: URL-encode so query strings (&, ?) don't break the request
    encoded=$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1], safe=''))" "$url")
    short=$(curl -s "https://tinyurl.com/api-create.php?url=$encoded")
    echo "[+] Short link: $short"
}

cmd_status() {
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "[+] Server running (PID: $pid)"
            echo "[+] Dashboard: http://localhost:5000"
            return
        fi
        rm -f "$PID_FILE"
        echo "[!] Stale PID file removed"
    fi
    echo "[!] Server not running"
}

case "$1" in
    setup) cmd_setup ;;
    server) cmd_server "$@" ;;
    stop) cmd_stop ;;
    generate) cmd_generate ;;
    list) cmd_list ;;
    dashboard) cmd_dashboard ;;
    export) cmd_export "$@" ;;
    shorten) cmd_shorten "$@" ;;
    status) cmd_status ;;
    *) help_menu ;;
esac