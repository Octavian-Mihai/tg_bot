from internbot.storage import Storage


def test_new_jobs_pass_through(tmp_path, make_job):
    with Storage(str(tmp_path / "t.db")) as s:
        jobs = [make_job(1), make_job(2)]
        assert s.filter_new(jobs) == jobs


def test_marked_jobs_are_not_returned_again(tmp_path, make_job):
    with Storage(str(tmp_path / "t.db")) as s:
        a, b = make_job(1), make_job(2)
        s.mark_seen([a])
        assert s.filter_new([a, b]) == [b]


def test_filter_new_does_not_mark_seen(tmp_path, make_job):
    with Storage(str(tmp_path / "t.db")) as s:
        job = make_job(1)
        s.filter_new([job])
        assert s.filter_new([job]) == [job]


def test_duplicates_within_one_batch_are_dropped(tmp_path, make_job):
    with Storage(str(tmp_path / "t.db")) as s:
        assert s.filter_new([make_job(1), make_job(1)]) == [make_job(1)]


def test_seen_state_persists_across_connections(tmp_path, make_job):
    path = str(tmp_path / "t.db")
    with Storage(path) as s:
        s.mark_seen([make_job(1)])
    with Storage(path) as s:
        assert s.filter_new([make_job(1)]) == []


def test_mark_seen_twice_is_harmless(tmp_path, make_job):
    with Storage(str(tmp_path / "t.db")) as s:
        s.mark_seen([make_job(1)])
        s.mark_seen([make_job(1)])
        assert s.is_seen(make_job(1))


def test_same_posting_from_another_source_is_treated_as_seen(tmp_path, make_job):
    with Storage(str(tmp_path / "t.db")) as s:
        board = make_job(1, id="greenhouse:acme:9", company="Acme", title="Software Developer Intern")
        s.mark_seen([board])
        adz = make_job(2, id="adzuna:77", company="ACME", title="software developer intern")
        assert s.filter_new([adz]) == []


def test_cross_source_duplicate_within_batch_keeps_first(tmp_path, make_job):
    with Storage(str(tmp_path / "t.db")) as s:
        board = make_job(1, id="greenhouse:acme:9")
        adz = make_job(2, id="adzuna:77")
        assert s.filter_new([board, adz]) == [board]


def test_old_db_without_key_column_is_migrated(tmp_path, make_job):
    import sqlite3

    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE seen_jobs (id TEXT PRIMARY KEY, title TEXT NOT NULL, company TEXT NOT NULL, "
        "url TEXT NOT NULL, first_seen TEXT NOT NULL)"
    )
    conn.execute("INSERT INTO seen_jobs VALUES ('adzuna:1','t','c','u','2026-01-01')")
    conn.commit()
    conn.close()
    with Storage(path) as s:
        assert s.filter_new([make_job(1)]) == []  # old row still matches by id
        assert s.filter_new([make_job(2)]) == [make_job(2)]


def test_same_title_from_one_source_stays_distinct(tmp_path, make_job):
    with Storage(str(tmp_path / "t.db")) as s:
        a, b = make_job(1, id="greenhouse:acme:1"), make_job(2, id="greenhouse:acme:2")
        assert s.filter_new([a, b]) == [a, b]
        s.mark_seen([a])
        assert s.filter_new([b]) == [b]
