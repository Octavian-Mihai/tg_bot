from internbot.formatting import format_job, format_messages


def test_format_job_has_title_company_location_url(make_job):
    text = format_job(make_job(1, title="Backend Intern", company="Coveo"))
    assert "Backend Intern" in text
    assert "Coveo — Montréal, QC" in text
    assert "https://example.com/1" in text


def test_format_job_without_location(make_job):
    assert " — " not in format_job(make_job(1, location=""))


def test_no_jobs_means_no_messages():
    assert format_messages([]) == []


def test_header_pluralization(make_job):
    assert format_messages([make_job(1)])[0].startswith("1 new internship posting\n")
    assert format_messages([make_job(1), make_job(2)])[0].startswith("2 new internship postings\n")


def test_small_batch_is_a_single_message(make_job):
    assert len(format_messages([make_job(i) for i in range(5)])) == 1


def test_long_batch_is_split_and_every_job_kept(make_job):
    jobs = [make_job(i) for i in range(60)]
    messages = format_messages(jobs, limit=500)
    assert len(messages) > 1
    assert all(len(m) <= 500 for m in messages)
    joined = "\n".join(messages)
    assert all(j.url in joined for j in jobs)


def test_oversized_single_entry_is_truncated(make_job):
    messages = format_messages([make_job(1, title="x" * 5000)], limit=500)
    assert all(len(m) <= 500 for m in messages)
