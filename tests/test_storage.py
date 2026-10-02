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
        assert s.is_seen("adzuna:1")
