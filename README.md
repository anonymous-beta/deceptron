# DECEPTRON

[![DECEPTRON](Decep.png)](Decep.png)

**Phishing-based Geolocation Tracker**

Red Team Geospatial Intelligence Framework — v1.1

[@anonymous-beta](https://github.com/anonymous-beta)

---

## what is this

DECEPTRON is a lightweight red team framework that generates phishing campaigns
to capture precise geolocation data from targets. It builds campaign pages from
realistic templates, hosts them, collects GPS/WiFi/IP location data, and
visualizes everything on a live satellite map dashboard.

Built for authorized security assessments, phishing simulations, and social
engineering engagements. Nothing here is magic — it's just geolocation APIs, a
Flask server, and some HTML that doesn't look like it was made in 2004.

## features

- **campaign generator** — builds phishing pages from realistic brand templates
  (Facebook, Google, Microsoft, security alert, system update, custom)
- **live collector** — receives geolocation data via POST, stores in SQLite
- **satellite dashboard** — real-time map with ESRI satellite imagery,
  color-coded markers, campaign filters
- **session tracking** — tracks unique sessions, hit counts, timestamps
- **auto fallback** — GPS → IP geolocation via ipapi if permission is denied
- **ftp deploy** — auto-uploads generated pages to your web host
- **data export** — dump everything as JSON or CSV
- **link obfuscation** — built-in URL shortener
- **hardened collector** — input validation, server-side timestamps,
  XSS-safe dashboard popups, DB auto-initialization

## what's new in v1.1

- **brand templates** — `facebook`, `google` and `microsoft` join the roster,
  with inline SVG logos (no external requests, no IP leaks to third parties)
- **loading states** — buttons show "verifying…" states that hold the page
  while the geolocation permission prompt is on screen
- **stability fixes** — the server no longer crashes on a missing DB; malformed
  POSTs get a clean 400 instead of a 500
- **dashboard hardening** — campaign IDs, session IDs and user agents are
  HTML-escaped in map popups (no stored XSS in your own dashboard)
- **quote-safe tracker injection** — URLs and campaign names with special
  characters no longer break the injected script
- **sane defaults** — bad/missing coordinates no longer drop "Null Island"
  pins; timestamps fall back to server time
- **unified banner** — the ASCII art lives in `banner.py` and is shared by the
  CLI, setup and server, with automatic fallback on narrow terminals

## quick start

```bash
# clone it
git clone https://github.com/anonymous-beta/deceptron.git
cd deceptron

# setup (creates dirs, installs deps, inits db)
chmod +x setup.sh
./setup.sh

# edit config.json with your host details
nano config.json

# start the collector + dashboard
./deceptron.sh server
```

Open `http://localhost:5000` in your browser. That's your dashboard.

## generating a campaign

```bash
./deceptron.sh generate
```

It'll ask you:

- campaign name (e.g. `test1`)
- template type (`facebook`, `google`, `microsoft`, `security`, `update`, or `custom`)
- redirect URL (where the target goes after capture)

Then it generates the page, injects the tracking script, uploads via FTP if
configured, and prints a tracking link.

Send that link. When the target opens it, their browser asks for location
permission. If they allow, you get GPS coordinates. If they deny, you get an
IP-based location (city-level). Either way, a pin drops on your dashboard.

## templates

| template   | look                          | best for                          |
|------------|-------------------------------|-----------------------------------|
| `facebook` | Facebook login (SVG logo)     | social media credential phishing scenarios |
| `google`   | Google-style sign-in          | account credential phishing scenarios |
| `microsoft`| Microsoft 365 sign-in         | corporate / O365 phishing scenarios |
| `update`   | system security update        | device compromise simulations     |
| `security` | unauthorized access alert     | account takeover scenarios        |
| `custom`   | your own HTML                 | anything else                     |

All brand templates are self-contained single files with inline SVG logos and
mobile-first CSS. Custom templates take raw HTML — the tracker script is
auto-injected before `</body>`.

## dashboard

- **ESRI satellite tiles** — real satellite imagery, not basic street maps
- **color-coded markers** — green (GPS), yellow (WiFi), red (IP fallback)
- **click any marker** — shows campaign, session, accuracy, user agent, timestamp
- **campaign filter** — isolate one campaign or view all
- **auto-refresh** — updates every 10 seconds
- **export buttons** — JSON or CSV download

## config.json

```json
{
    "ftp_host": "ftp.your-domain.com",
    "ftp_user": "username",
    "ftp_pass": "password",
    "ftp_path": "/public_html",
    "base_url": "https://your-domain.com",
    "server_host": "0.0.0.0",
    "server_port": 5000,
    "collector_url": "https://your-domain.com/log",
    "map_tile_url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "db_path": "db/hits.db"
}
```

If you don't set FTP credentials, generated pages are saved to
`generated/<campaign>/` for manual upload.

## https is required

Most browsers block geolocation over plain HTTP, and a browser on an HTTPS page
will refuse to POST to an HTTP collector (mixed content). Two ways to get TLS:

- **reverse proxy** — put nginx in front of the server with Let's Encrypt, and
  proxy `/` and `/log` to `127.0.0.1:5000`. Point `collector_url` at
  `https://your-domain.com/log`.
- **quick tunnel** — for local testing, `cloudflared tunnel --url
  http://localhost:5000` gives you a free HTTPS URL to use as `collector_url`.

## file layout

```
deceptron/
├── setup.sh           # environment bootstrap
├── deceptron.sh       # main CLI
├── server.py          # collector + dashboard (Flask)
├── init_db.py         # shared SQLite schema initialization
├── banner.py          # ASCII banner module (shared by CLI/server)
├── requirements.txt   # python dependencies
├── config.json        # created by setup.sh
├── templates/         # campaign page templates
├── generated/         # generated campaign pages
└── db/                # hits.db
```

## termux / android

Works on Termux. Install deps first:

```bash
pkg update && pkg upgrade
pkg install python git
pip install -r requirements.txt
```

Then run the same setup commands.

## commands

```
./deceptron.sh setup       # init environment
./deceptron.sh server      # start collector + dashboard
./deceptron.sh generate    # create new campaign
./deceptron.sh list        # show all campaigns
./deceptron.sh dashboard   # open dashboard in browser
./deceptron.sh export      # export data (json/csv)
./deceptron.sh shorten     # obfuscate a link
./deceptron.sh status      # check if server is running
./deceptron.sh help        # show this menu
```

## important notes

- **https required** — see the section above; without TLS the GPS prompt and
  the collector POST will both be blocked by the target's browser.
- **permission-based** — the target must grant geolocation access for GPS
  precision. IP fallback is automatic but less accurate.
- **legal** — only use this on systems you own or have explicit written
  permission to test. This tool is for authorized red team operations, not
  stalking.

## credits

Built by **anonymous-beta**

- github: [https://github.com/anonymous-beta](https://github.com/anonymous-beta)
- project: DECEPTRON v1.1

If you fork it, credit the original. That's all I ask.

## license

MIT — see `LICENSE` file. Use at your own risk.