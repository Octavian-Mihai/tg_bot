"""Local dashboard: browse what the bot found, tag postings Applied / Skipped, see your numbers.

    python -m internbot.site            # fetches the latest data, serves http://127.0.0.1:8765

Nothing leaves your machine. The bot's postings come from the `state` branch (the same DB the
GitHub run keeps); your Applied / Skipped marks live in local/applications.db, which a refresh
never touches. Stdlib only.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "local"
JOBS_DB = LOCAL / "jobs.db"
APPS_DB = LOCAL / "applications.db"
PAGE = Path(__file__).with_name("site_page.html")
STATUSES = ("applied", "skipped")
CLOSED_AFTER = 45  # seconds without a page heartbeat before --exit-when-closed stops the server
_last_ping = [time.monotonic()]

_APPS_SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    job_id     TEXT PRIMARY KEY,
    status     TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    applied_at TEXT,
    title      TEXT NOT NULL, company TEXT NOT NULL, location TEXT NOT NULL, url TEXT NOT NULL,
    resume     TEXT NOT NULL, family TEXT NOT NULL, place TEXT NOT NULL
)
"""


def fetch_state() -> str:
    """Pull the bot's latest DB from the `state` branch into local/jobs.db. Returns a status line."""
    LOCAL.mkdir(exist_ok=True)
    try:
        subprocess.run(["git", "fetch", "-q", "origin", "+state:refs/remotes/origin/state"],
                       cwd=ROOT, check=True, capture_output=True, timeout=60)
        blob = subprocess.run(["git", "show", "origin/state:seen_jobs.db"], cwd=ROOT,
                              check=True, capture_output=True, timeout=60).stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return f"could not fetch the bot's data ({type(exc).__name__}); showing the last copy"
    tmp = JOBS_DB.with_suffix(".tmp")
    tmp.write_bytes(blob)
    tmp.replace(JOBS_DB)
    return "ok"


def _apps() -> sqlite3.Connection:
    LOCAL.mkdir(exist_ok=True)
    conn = sqlite3.connect(APPS_DB)
    conn.row_factory = sqlite3.Row
    conn.execute(_APPS_SCHEMA)
    return conn


LEGACY_LIMIT = 30


def _legacy_rows(src: sqlite3.Connection, have: set[str]) -> list[dict]:
    """The latest postings the bot sent before it kept full details: title, company and link
    only, so location is unknown and the CV is chosen from the title alone."""
    from internbot.models import Job
    from internbot.profile import load_profile
    from internbot.resume import choose_resume

    profile = load_profile()
    out = []
    latest = src.execute("SELECT id, title, company, url, first_seen FROM seen_jobs ORDER BY first_seen DESC, rowid DESC LIMIT ?",
                         (LEGACY_LIMIT,)).fetchall()
    detailed = {(c.strip().lower(), t.strip().lower()) for c, t in src.execute("SELECT company, title FROM postings")}
    for r in latest:
        if r["id"] in have or (r["company"].strip().lower(), r["title"].strip().lower()) in detailed:
            continue
        choice = choose_resume(Job(id=r["id"], title=r["title"], company=r["company"], location="", url=r["url"],
                                   source=r["id"].split(":")[0]), profile)
        out.append({"id": r["id"], "title": r["title"], "company": r["company"], "location": "", "url": r["url"],
                    "source": r["id"].split(":")[0], "term": "", "posted": "", "chance": 0, "quality": 0,
                    "resume": choice.variant, "family": choice.family, "place": "unknown", "rank": 0,
                    "first_seen": r["first_seen"]})
    return out


def bot_times() -> dict:
    """When the bot last checked the job boards, and when it last found something new."""
    out = {"last_run": None, "last_new": None}
    if not JOBS_DB.exists():
        return out
    src = sqlite3.connect(JOBS_DB)
    try:
        row = src.execute("SELECT value FROM meta WHERE key = 'last_run'").fetchone()
        out["last_run"] = row[0] if row else None
        row = src.execute("SELECT MAX(first_seen) FROM seen_jobs").fetchone()
        out["last_new"] = row[0] if row else None
    except sqlite3.OperationalError:
        pass
    finally:
        src.close()
    return out


def load_jobs() -> list[dict]:
    """Every posting the bot sent, newest batch first, each with your status (or null)."""
    rows: list[dict] = []
    if JOBS_DB.exists():
        src = sqlite3.connect(JOBS_DB)
        src.row_factory = sqlite3.Row
        try:
            rows = [dict(r) for r in src.execute("SELECT * FROM postings ORDER BY first_seen DESC, rank")]
            rows += _legacy_rows(src, {r["id"] for r in rows})
        except sqlite3.OperationalError:  # the bot hasn't saved a run with the new table yet
            pass
        finally:
            src.close()
    with _apps() as conn:
        status = {r["job_id"]: dict(r) for r in conn.execute("SELECT * FROM applications")}
    for row in rows:
        mark = status.get(row["id"])
        row["status"] = mark["status"] if mark else None
        row["applied_at"] = mark["applied_at"] if mark else None
    # A posting can leave the bot's data but your applications must stay in the stats.
    known = {r["id"] for r in rows}
    for mark in status.values():
        if mark["job_id"] not in known:
            rows.append({"id": mark["job_id"], "title": mark["title"], "company": mark["company"],
                         "location": mark["location"], "url": mark["url"], "resume": mark["resume"],
                         "family": mark["family"], "place": mark["place"], "status": mark["status"],
                         "applied_at": mark["applied_at"], "first_seen": mark["updated_at"], "posted": "",
                         "chance": 0, "quality": 0, "rank": 0, "term": "", "source": ""})
    return rows


def set_status(job_id: str, status: str | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _apps() as conn:
        if status is None:
            conn.execute("DELETE FROM applications WHERE job_id = ?", (job_id,))
            return
        if status not in STATUSES:
            raise ValueError("bad status")
        job = next((j for j in load_jobs() if j["id"] == job_id), None)
        if job is None:
            raise KeyError(job_id)
        prior = conn.execute("SELECT applied_at FROM applications WHERE job_id = ?", (job_id,)).fetchone()
        applied_at = (prior["applied_at"] if prior and prior["applied_at"] else now) if status == "applied" else None
        conn.execute(
            "INSERT OR REPLACE INTO applications VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (job_id, status, now, applied_at, job["title"], job["company"], job["location"], job["url"],
             job["resume"], job["family"], job["place"]),
        )


def applications_csv() -> str:
    """Your applications as CSV, which Excel opens directly."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Status", "Applied on", "Company", "Title", "Location", "Place", "Role family", "CV", "Link"])
    with _apps() as conn:
        for r in conn.execute("SELECT * FROM applications ORDER BY COALESCE(applied_at, updated_at) DESC"):
            w.writerow([r["status"], (r["applied_at"] or "")[:10], r["company"], r["title"], r["location"],
                        r["place"], r["family"], r["resume"], r["url"]])
    return out.getvalue()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the terminal quiet
        pass

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json")

    def do_GET(self):
        if self.path == "/":
            self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/jobs":
            self._json({"jobs": load_jobs(), **bot_times()})
        elif self.path == "/api/ping":
            _last_ping[0] = time.monotonic()
            self._json({"ok": True})
        elif self.path == "/api/refresh":
            self._json({"result": fetch_state(), "jobs": load_jobs(), **bot_times()})
        elif self.path == "/export.csv":
            self._send(200, ("﻿" + applications_csv()).encode(), "text/csv; charset=utf-8",
                       {"Content-Disposition": 'attachment; filename="applications.csv"'})
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        # Another site open in your browser must not be able to mark things for you.
        if self.headers.get("Origin") not in (None, f"http://{self.headers.get('Host')}"):
            return self._send(403, b"forbidden", "text/plain")
        if self.path != "/api/status":
            return self._send(404, b"not found", "text/plain")
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
            set_status(str(body["id"]), body.get("status"))
        except (ValueError, KeyError, TypeError):
            return self._json({"error": "bad request"}, 400)
        self._json({"ok": True})


def main() -> int:
    parser = argparse.ArgumentParser(description="Local internship dashboard")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-fetch", action="store_true", help="skip pulling the latest data")
    parser.add_argument("--exit-when-closed", action="store_true", help="stop when the page is closed")
    parser.add_argument("--no-open", action="store_true", help="don't open the browser")
    args = parser.parse_args()
    if not args.no_fetch:
        print("Fetching the bot's latest data...", fetch_state())
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"Dashboard at {url}  (Ctrl+C to stop)")
    if not args.no_open:
        webbrowser.open(url)
    if args.exit_when_closed:
        def watch() -> None:
            time.sleep(60)  # the page needs time to open and send its first heartbeat
            while time.monotonic() - _last_ping[0] < CLOSED_AFTER:
                time.sleep(5)
            server.shutdown()
        threading.Thread(target=watch, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
