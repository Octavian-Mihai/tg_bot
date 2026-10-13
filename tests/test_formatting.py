from internbot.formatting import format_empty, format_job, format_messages, sources_footer
from internbot.ranking import rank_jobs
from datetime import datetime


def ranked(make_job, profile, n=1, **kw):
    return rank_jobs([make_job(i, **kw) for i in range(1, n + 1)], profile)


def test_format_job_has_rank_title_company_location_url_and_resume(make_job, profile):
    text = format_job(3, ranked(make_job, profile, title="Backend Intern", company="Coveo")[0])
    assert text.startswith("3. <b>Backend Intern</b>")
    assert "Coveo — Montréal, QC" in text and "https://example.com/1" in text
    assert "chance" in text and "quality" in text and "Résumé: <i>backend" in text


def test_format_job_shows_the_term_and_title_only_marker(make_job, profile):
    text = format_job(1, ranked(make_job, profile, term="summer-2027 winter-2027")[0])
    assert "Summer 2027 · Winter 2027" in text and "title only" in text


def test_format_job_without_location(make_job, profile):
    assert " — " not in format_job(1, ranked(make_job, profile, location="")[0])


def test_no_jobs_means_no_messages():
    assert format_messages([]) == []


def test_header_pluralization(make_job, profile):
    assert format_messages(ranked(make_job, profile, 1))[0].startswith("🆕 1 new internship posting,")
    assert format_messages(ranked(make_job, profile, 2))[0].startswith("🆕 2 new internship postings,")


def test_postings_are_grouped_per_message(make_job, profile):
    items = ranked(make_job, profile, 45)
    messages = format_messages(items, per_message=20)
    assert len(messages) == 3
    assert "(message 1/3)" in messages[0] and "(message 3/3)" in messages[2]
    assert "\n21. " in messages[1] and "\n45. " in messages[2]
    assert all(i.job.url in "\n".join(messages) for i in items)


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


def test_format_job_escapes_html(make_job, profile):
    text = format_job(1, ranked(make_job, profile, title="R&D <Intern>")[0])
    assert "<b>R&amp;D &lt;Intern&gt;</b>" in text


def test_montreal_postings_rank_before_better_scoring_others(make_job, profile):
    jobs = [make_job(1, location="Toronto, ON"), make_job(2, location="Montréal, QC")]
    order = [r.job.location for r in rank_jobs(jobs, profile)]
    assert order[0] == "Montréal, QC"


def test_posted_ago_wording():
    from datetime import date
    from internbot.formatting import posted_ago
    today = date(2026, 10, 13)
    assert posted_ago("2026-10-13", today) == "posted today"
    assert posted_ago("2026-10-11", today) == "posted 2d ago"
    assert posted_ago("", today) == "" and posted_ago("2027-01-01", today) == ""


def test_priority_company_and_newest_break_ties(make_job, profile):
    jobs = [make_job(1, company="Other"), make_job(2, company="Coveo"), make_job(3, company="Other")]
    order = [r.job.company for r in rank_jobs(jobs, profile, ("coveo",))]
    assert order[0] == "Coveo"
    from dataclasses import replace
    old, new = replace(make_job(4), posted="2026-01-01"), replace(make_job(5), posted="2026-10-01")
    assert rank_jobs([old, new], profile)[0].job.id == new.id


def test_every_numbered_posting_gets_applied_and_skip_buttons(make_job, profile):
    msg = format_messages(ranked(make_job, profile, 3))[0]
    from internbot.formatting import action_keyboard
    kb = action_keyboard(msg)["inline_keyboard"]
    assert [r[0]["callback_data"] for r in kb] == ["a:1", "a:2", "a:3"]
    assert all(len(r[0]["callback_data"]) < 64 for r in kb) and action_keyboard("nothing numbered") is None
