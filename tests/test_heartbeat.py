import sqlite3

from internbot.heartbeat import build_message
from internbot.storage import Storage


def test_stats_counts_recent_and_total(tmp_path, make_job):
    path = str(tmp_path / "t.db")
    with Storage(path) as s:
        s.mark_seen([make_job(1), make_job(2), make_job(3)])
        s.conn.execute(
            "UPDATE seen_jobs SET first_seen = '2000-01-01T00:00:00+00:00' WHERE id = 'adzuna:3'"
        )
        s.conn.commit()
        assert s.stats(days=7) == (2, 3)


def test_stats_on_empty_db(tmp_path):
    with Storage(str(tmp_path / "t.db")) as s:
        assert s.stats() == (0, 0)


def test_message_contains_the_numbers():
    msg = build_message(recent=4, total=120, n_companies=8)
    assert "4" in msg and "120" in msg and "8 company boards" in msg
