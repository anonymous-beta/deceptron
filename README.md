<p align="center">
  <img src="Icon.png" width="180" alt="DECEPTRON">
</p>

<h1 align="center">DECEPTRON</h1>
<p align="center">
  <b>Phishing-based Geolocation Tracker</b><br>
  <sub>Red Team Geospatial Intelligence Framework — v1.0</sub>
</p>

<p align="center">
  <a href="https://github.com/anonymous-beta">@anonymous-beta</a>
</p>

---

## what is this

DECEPTRON is a lightweight red team framework that generates phishing campaigns to capture precise geolocation data from targets. it builds campaign pages, hosts them, collects GPS/WiFi/IP location data, and visualizes everything on a live satellite map dashboard.

built for authorized security assessments, bug bounty recon, and social engineering simulations. nothing here is magic — it's just geolocation APIs, a flask server, and some html that doesn't look like it was made in 2004.

---

## features

- **campaign generator** — builds phishing pages from templates (login, update, security, custom)
- **live collector** — receives geolocation data via POST, stores in sqlite
- **satellite dashboard** — real-time map with esri satellite imagery, color-coded markers, campaign filters
- **session tracking** — tracks unique sessions, hit counts, timestamps
- **auto fallback** — GPS → IP geolocation via ipapi if permission denied
- **ftp deploy** — auto-uploads generated pages to your web host
- **data export** — dump everything as json or csv
- **link obfuscation** — built-in url shortener

---

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

open `http://localhost:5000` in your browser. that's your dashboard.

---

## generating a campaign

```bash
./deceptron.sh generate
```

it'll ask you:
- campaign name (e.g. `test1`)
- template type (`login`, `update`, `security`, or `custom`)
- redirect url (where the target goes after capture)

then it generates the page, injects the tracking script, uploads via ftp, and spits out a tracking link.

send that link. when someone clicks, their browser asks for location permission. if they allow, you get GPS coords. if they deny, you get ip-based location (city-level). either way, a pin drops on your dashboard.

---

## templates

| template | look | best for |
|----------|------|----------|
| `login` | google-style sign-in | credential phishing scenarios |
| `update` | system security update | device compromise simulations |
| `security` | unauthorized access alert | account takeover scenarios |
| `custom` | your own html | anything else |

custom templates take raw html. the script auto-injects the tracker before `</body>`.

---

## dashboard

- **esri satellite tiles** — real satellite imagery, not basic street maps
- **color-coded markers** — green (GPS), yellow (WiFi), red (IP fallback)
- **click any marker** — shows campaign, session, accuracy, user agent, timestamp
- **campaign filter** — isolate one campaign or view all
- **auto-refresh** — updates every 10 seconds
- **export buttons** — json or csv download

---

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

if you don't set ftp credentials, generated pages are saved to `generated/<campaign>/` for manual upload.

---

## termux / android

works on termux. install deps first:

```bash
pkg update && pkg upgrade
pkg install python nodejs curl jq sqlite
pip install flask flask-cors requests
```

then run the same setup commands.

---

## commands

```bash
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

---

## important notes

- **https required** — most browsers block geolocation over http. use a host with ssl (infinityfree, 000webhost, etc.)
- **permission-based** — the target must grant geolocation access for GPS precision. ip fallback is automatic but less accurate.
- **legal** — only use this on systems you own or have explicit written permission to test. this tool is for authorized red team operations, not stalking.

---

## credits

built by **anonymous-beta**

- github: [https://github.com/anonymous-beta](https://github.com/anonymous-beta)
- project: DECEPTRON v1.0

if you fork it, credit the original. that's all i ask.

---

## license

MIT — see `LICENSE` file. use at your own risk.
