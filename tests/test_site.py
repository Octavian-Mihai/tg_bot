import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from internbot import site
from internbot.ranking import rank_jobs
from internbot.storage import Storage


@pytest.fixture
def served(tmp_path, monkeypatch, make_job, profile):
    monkeypatch.setattr(site, "LOCAL", tmp_path)
    monkeypatch.setattr(site, "JOBS_DB", tmp_path / "jobs.db")
    monkeypatch.setattr(site, "APPS_DB", tmp_path / "applications.db")
    ranked = rank_jobs([make_job(1, title="Backend Intern", location="Montréal, QC"),
                        make_job(2, location="Toronto, ON")], profile)
    with Storage(str(tmp_path / "jobs.db")) as s:
        s.save_postings(ranked)
    server = ThreadingHTTPServer(("127.0.0.1", 0), site.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def post(base, body, origin=None):
    req = urllib.request.Request(base + "/api/status", json.dumps(body).encode(), {"Content-Type": "application/json", **({"Origin": origin} if origin else {})})
    return urllib.request.urlopen(req)


def jobs(base):
    return json.load(urllib.request.urlopen(base + "/api/jobs"))["jobs"]


def test_mark_applied_skipped_and_undo(served):
    first = jobs(served)[0]
    assert first["status"] is None and first["place"] in ("montreal", "other")
    post(served, {"id": first["id"], "status": "applied"})
    row = next(j for j in jobs(served) if j["id"] == first["id"])
    assert row["status"] == "applied" and row["applied_at"]
    post(served, {"id": first["id"], "status": None})
    assert next(j for j in jobs(served) if j["id"] == first["id"])["status"] is None


def test_applications_survive_a_data_refresh_and_export_to_csv(served, tmp_path):
    jid = jobs(served)[0]["id"]
    post(served, {"id": jid, "status": "applied"})
    (tmp_path / "jobs.db").unlink()  # the bot's data is replaced/pruned
    assert any(j["id"] == jid and j["status"] == "applied" for j in jobs(served))
    csv_text = urllib.request.urlopen(served + "/export.csv").read().decode("utf-8-sig")
    assert csv_text.startswith("Status,Applied on") and "applied" in csv_text


def test_unknown_job_and_foreign_origin_are_rejected(served):
    with pytest.raises(urllib.error.HTTPError) as e:
        post(served, {"id": "nope:1", "status": "applied"})
    assert e.value.code == 400
    with pytest.raises(urllib.error.HTTPError) as e:
        post(served, {"id": jobs(served)[0]["id"], "status": "applied"}, origin="http://evil.example")
    assert e.value.code == 403


def test_postings_sent_before_details_were_kept_still_show_up(served, tmp_path):
    with Storage(str(tmp_path / "jobs.db")) as s:
        s.conn.execute("INSERT INTO seen_jobs (id,title,company,url,first_seen,key) VALUES ('lever:old','iOS Developer Intern','Ubisoft','https://x.test/old','2026-10-01T00:00:00+00:00','k')")
        s.conn.commit()
    old = next(j for j in jobs(served) if j["id"] == "lever:old")
    assert old["place"] == "unknown" and old["resume"] and old["location"] == ""
    post(served, {"id": "lever:old", "status": "applied"})
