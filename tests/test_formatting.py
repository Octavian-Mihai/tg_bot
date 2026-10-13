from internbot.formatting import format_empty, format_job, format_messages, sources_footer
from internbot.ranking import rank_jobs
from datetime import datetime


def ranked(make_job, profile, n=1, **kw):
    return rank_jobs([make_job(i, **kw) for i in range(1, n + 1)], profile)


def test_format_job_has_rank_title_company_location_url_and_resume(make_job, profile):
    text = format_job(3, ranked(make_job, profile, title="Backend Intern", company="Coveo")[0])
    assert text.startswith("3. Backend Intern")
    assert "Coveo — Montréal, QC" in text and "https://example.com/1" in text
    assert "chance" in text and "quality" in text and "Résumé: backend" in text


def test_format_job_shows_the_term_and_title_only_marker(make_job, profile):
    text = format_job(1, ranked(make_job, profile, term="summer-2027 winter-2027")[0])
    assert "Summer 2027 · Winter 2027" in text and "title only" in text


def test_format_job_without_location(make_job, profile):
    assert " — " not in format_job(1, ranked(make_job, profile, location="")[0])


def test_no_jobs_means_no_messages():
    assert format_messages([]) == []


def test_header_pluralization_and_queue_note(make_job, profile):
    assert format_messages(ranked(make_job, profile, 1))[0].startswith("🆕 1 new internship posting,")
    two = format_messages(ranked(make_job, profile, 2), queued=7)[0]
    assert two.startswith("🆕 2 new internship postings,") and "7 more waiting" in two


def test_small_batch_is_a_single_message(make_job, profile):
    assert len(format_messages(ranked(make_job, profile, 3))) == 1


def test_long_batch_is_split_and_every_job_kept(make_job, profile):
    items = ranked(make_job, profile, 60)
    messages = format_messages(items, limit=800)
    assert len(messages) > 1 and all(len(m) <= 800 for m in messages)
    joined = "\n".join(messages)
    assert all(i.job.url in joined for i in items)


def test_oversized_single_entry_is_truncated(make_job, profile):
    messages = format_messages(ranked(make_job, profile, title="x" * 5000), limit=500)
    assert all(len(m) <= 500 for m in messages)


def test_footer_is_appended(make_job, profile):
    assert format_messages(ranked(make_job, profile, 1), footer="Checked 20 sources")[-1].endswith("Checked 20 sources")


def test_empty_message_says_so_and_names_failures():
    text = format_empty(datetime(2026, 10, 13, 14, 5), 120, 19, 1, ["workday"])
    assert "no new internship postings" in text and "120 postings" in text and "workday" in text
    assert "failed" not in format_empty(datetime(2026, 10, 13, 14, 5), 1, 2, 0, [])
    assert "1 failed: lever" in sources_footer(5, 1, ["lever"])
