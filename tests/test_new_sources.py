import time

import pytest

from internbot.models import Job
from internbot.sources import (
    ats, bamboohr, discover, eightfold, github, hnhiring, icims, jobbank, levelsfyi, oracle, personio, phenom,
    recruitee, smartrecruiters, workable, workday,
)
from internbot.sources.base import Posting, flatten, parallel_map
from internbot.sources.common import build_job
from internbot.textutil import html_to_text


def P(*urls):
    return [Posting(u, "Co") for u in urls]


# ---- shared plumbing ---------------------------------------------------------------------------

def test_build_job_applies_title_place_and_term_gates():
    ok = dict(source="x", ident="1", company="Co", url="https://e/1", location="Montréal")
    assert build_job(title="Software Intern - Summer 2027", **ok).term == "summer-2027"
    assert build_job(title="Software Intern", **ok).term == "unstated"
    assert build_job(title="Account Executive", **ok) is None  # not an internship
    assert build_job(title="Software Intern", **{**ok, "location": "Toronto, ON"}) is None
    assert build_job(title="Software Intern - Fall 2026", **ok) is None  # wrong cycle
    assert build_job(title="Application Developer", kind="campus", **ok).id == "x:1"  # student-only sites
    assert build_job(title="Software Intern", **{**ok, "url": ""}) is None


def test_html_to_text_handles_escaped_and_real_html():
    assert html_to_text("&lt;p&gt;Hello &amp;amp; <b>bye</b>&lt;/p&gt;") == "Hello &amp; bye"
    assert html_to_text("<p>One</p><p>Two</p><script>x()</script>") == "One Two"
    assert html_to_text(None) == ""


def test_parallel_map_survives_failures_and_deadlines():
    def f(x):
        if x == 2:
            raise RuntimeError("dead board")
        return x * 10

    assert parallel_map([1, 2, 3], f, workers=2) == [10, None, 30]
    assert parallel_map([1, 2], f, deadline=time.monotonic() - 1) == [None, None]
    jobs, reachable = flatten([[Job("a:1", "t", "c", "l", "https://u/1", "a")], None, [Job("a:2", "t", "c", "l", "https://u/1", "a")]])
    assert len(jobs) == 1 and reachable == 2


# ---- harvesting board tokens ---------------------------------------------------------------------

def test_ats_tokens_come_from_apply_urls_and_demo_boards_are_ignored():
    t = ats.harvest_tokens([
        Posting("https://job-boards.greenhouse.io/haizelabs/jobs/123", "Haize Labs"),
        Posting("https://job-boards.greenhouse.io/embed/job_app?for=point72", "Point72"),
        Posting("https://grnh.se/a1b2c3", ""),
        Posting("https://jobs.ashbyhq.com/ellipsislabs/abc", "Ellipsis Labs"),
        Posting("https://jobs.lever.co/leverdemo/1", ""),
        Posting("https://jobs.lever.co/demodesk/1", ""),
        Posting("https://example.com/careers", ""),
    ])
    assert t["greenhouse"] == {"haizelabs": "Haize Labs", "point72": "Point72"}
    assert t["ashby"] == {"ellipsislabs": "Ellipsis Labs"} and t["lever"] == {"demodesk": ""}


def test_first_company_name_wins_and_later_blanks_do_not_erase_it():
    t = ats.harvest_tokens([Posting("https://jobs.lever.co/acme/1", ""), Posting("https://jobs.lever.co/acme/2", "Acme Inc"),
                            Posting("https://jobs.lever.co/acme/3", "Other")])
    assert t["lever"] == {"acme": "Acme Inc"}


def test_ats_scrape_skips_configured_boards_and_disabled_ats(monkeypatch):
    seen = []
    monkeypatch.setitem(ats.FETCHERS, "lever", lambda token, company: seen.append(("lever", token)) or [])
    monkeypatch.setitem(ats.FETCHERS, "ashby", lambda token, company: seen.append(("ashby", token)) or [])
    ats.scrape(P("https://jobs.lever.co/mine/1", "https://jobs.lever.co/new/1", "https://jobs.ashbyhq.com/a/1"),
               {"lever"}, 2, None, skip={("lever", "mine")})
    assert seen == [("lever", "new")]


def test_workday_targets_both_url_shapes():
    ts = workday.harvest_targets([
        Posting("https://shopify.wd3.myworkdayjobs.com/en-US/External/job/Montreal/Intern_R1", "Shopify"),
        Posting("https://wd5.myworkdaysite.com/recruiting/td/TD_Bank_Careers/job/X", "TD"),
        Posting("https://acme.wd1.myworkdayjobs.com/jobs/job/x", "Acme"),  # "jobs" is not a site
    ])
    by = {t.tenant: t for t in ts}
    assert set(by) == {"shopify", "td"}
    assert by["shopify"] == workday.Target("shopify", "wd3", "External", "myworkdayjobs", "Shopify")
    assert workday.job_url(by["shopify"], "/job/A") == "https://shopify.wd3.myworkdayjobs.com/External/job/A"
    assert workday.job_url(by["td"], "/job/A") == "https://wd5.myworkdaysite.com/recruiting/td/TD_Bank_Careers/job/A"


def test_campus_sites_are_recognised_without_matching_internal_or_international():
    r = workday._CAMPUS_SITE
    assert r.search("UVAStudentJobs") and r.search("earlycareers") and r.search("Campus")
    assert not r.search("spgi_internal") and not r.search("HUBInternational")


def test_workday_scrape_site_filters_and_reads_descriptions(monkeypatch):
    t = workday.Target("bank", "wd3", "Campus", "myworkdayjobs", "Bank")
    monkeypatch.setattr(workday, "post_json", lambda url, body, **kw: {"total": 3, "jobPostings": [
        {"title": "Application Developer", "locationsText": "Montreal, QC", "externalPath": "/job/1"},  # campus site: no "intern" needed
        {"title": "Software Developer", "locationsText": "Toronto, ON", "externalPath": "/job/2"},
        {"title": "Marketing Specialist", "locationsText": "Montreal", "externalPath": "/job/3"},
    ]} if body["offset"] == 0 else {"total": 3, "jobPostings": []})
    monkeypatch.setattr(workday, "get_json", lambda url, **kw: {"jobPostingInfo": {"jobDescription": "<p>Summer 2027 term</p>"}})
    jobs = workday.scrape_site(t)
    assert [j.title for j in jobs] == ["Application Developer"] and jobs[0].term == "summer-2027"
    assert jobs[0].url == "https://bank.wd3.myworkdayjobs.com/Campus/job/1" and jobs[0].source == "workday"


def test_oracle_smartrecruiters_and_friends_harvest_their_own_hosts():
    assert oracle.harvest_sites(P("https://eibc.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1/job/9")) == [
        oracle.Site("eibc.fa.us2.oraclecloud.com", "CX_1", "Co")]
    assert smartrecruiters.harvest_companies(P("https://jobs.smartrecruiters.com/Ubisoft/123", "https://jobs.smartrecruiters.com/oneclick-ui/x")) == {"Ubisoft": "Co"}
    assert workable.harvest_tenants(P("https://apply.workable.com/acme/j/ABC/", "https://apply.workable.com/api/x", "https://foo.workable.com/")) == {"acme": "Co", "foo": "Co"}
    assert recruitee.harvest_tenants(P("https://acme.recruitee.com/o/x", "https://www.recruitee.com/")) == {"acme": "Co"}
    assert bamboohr.harvest_tenants(P("https://acme.bamboohr.com/careers/1", "https://www.bamboohr.com/")) == {"acme": "Co"}
    assert icims.harvest_sites(P("https://careers-acme.icims.com/jobs/1/x/job", "https://www.icims.com/")) == {"careers-acme.icims.com": "Co"}
    assert personio.harvest_tenants(P("https://acme.jobs.personio.de/job/1", "https://x.jobs.personio.com/")) == {"acme": ("Co", "de"), "x": ("Co", "com")}
    sites = eightfold.harvest_sites(P("https://bnymellon.eightfold.ai/careers/job/1"), overrides={"bnymellon": "bny.com"})
    assert sites == {"bnymellon.eightfold.ai": {"company": "Co", "domain": "bny.com"}}
    assert eightfold.harvest_sites(P("https://acme.eightfold.ai/x"), overrides={})["acme.eightfold.ai"]["domain"] == "acme.com"


def test_icims_reads_the_schema_org_posting():
    html = '<script type="application/ld+json">{"@type":"JobPosting","title":"Dev Intern","jobLocation":[{"address":{"addressLocality":"Montreal","addressRegion":"QC","addressCountry":"CA"}}]}</script>'
    ld = icims._job_posting_ld("<html>" + html + "</html>")
    assert ld["title"] == "Dev Intern" and icims._ld_location(ld) == "Montreal, QC, CA"
    assert icims._job_posting_ld("<script type='application/ld+json'>{bad</script>") is None
    assert icims._slug_to_title("Software-Intern%20-%20Montreal") == "Software Intern Montreal"


def test_personio_reads_the_xml_feed(monkeypatch):
    xml = """<workzag-jobs><position><id>7</id><name>Software Intern</name><office>Montreal</office>
      <additionalOffices><office>Paris</office></additionalOffices>
      <jobDescriptions><jobDescription><name>x</name><value>&lt;p&gt;Winter 2027 internship&lt;/p&gt;</value></jobDescription></jobDescriptions>
      </position><position><id>8</id><name>Chef</name><office>Montreal</office></position></workzag-jobs>"""
    monkeypatch.setattr(personio, "get_text", lambda url, **kw: xml)
    jobs = personio.scrape_tenant("acme", "Acme", "de")
    assert [j.id for j in jobs] == ["personio:https://acme.jobs.personio.de/job/7"] and jobs[0].term == "winter-2027"


def test_phenom_pages_the_widgets_api(monkeypatch):
    monkeypatch.setattr(phenom, "post_json", lambda url, body, **kw: {"refineSearch": {"totalHits": 2, "data": {"jobs": [
        {"jobSeqNo": "A1", "title": "Software Developer Intern", "location": "Montreal, Quebec, Canada", "description": "<p>Summer 2027</p>"},
        {"jobSeqNo": "A2", "title": "Software Developer Intern", "location": "Calgary, Alberta, Canada"}]}}}
        if body["from"] == 0 else {"refineSearch": {"totalHits": 2, "data": {"jobs": []}}})
    jobs = phenom.scrape_site({"host": "jobs.bell.ca", "company": "Bell"})
    assert len(jobs) == 1 and jobs[0].company == "Bell" and jobs[0].term == "summer-2027"
    assert phenom.load_sites() and phenom.load_sites()[0]["host"] == "jobs.bell.ca"


# ---- feeds ----------------------------------------------------------------------------------------

LISTINGS = [
    {"company_name": "Shopify", "title": "Software Engineering Intern", "locations": ["Montreal, QC"], "url": "https://s/1", "season": "Summer", "active": True},
    {"company_name": "Ciena", "title": "Network Software Intern", "locations": ["Ottawa, ON"], "url": "https://s/2", "season": "Summer"},
    {"company_name": "Bell", "title": "Developer Co-op", "locations": ["Montreal"], "url": "https://s/3", "season": "Winter"},
    {"company_name": "Old", "title": "Software Intern", "locations": ["Montreal"], "url": "https://s/4", "season": "Fall"},
    {"company_name": "Dead", "title": "Software Intern", "locations": ["Montreal"], "url": "https://s/5", "season": "Summer", "active": False},
]


def test_listing_feed_keeps_summer_and_winter_in_montreal_only():
    board = github.Board("x/Summer2027", "u", "listings", hint_year=2027)
    jobs = github.parse_listings(LISTINGS, board)
    assert [(j.company, j.term) for j in jobs] == [("Shopify", "summer-2027"), ("Bell", "winter-2027")]


MARKDOWN = """
| Company | Role | Location | Application/Link | Date Posted |
| --- | --- | --- | --- | --- |
| **[Shopify](https://shopify.com)** | Software Engineering Intern | Montreal, QC | <a href="https://jobs.example/1"><img src="x.png"></a> | Sep 1 |
| ↳ | Security Intern | Montreal<br>Toronto | [Apply](https://jobs.example/2) | Sep 1 |
| Acme | Backend Intern (Fall 2026) | Montreal | [![Apply](https://img.shields.io/badge/a.svg)](https://jobs.example/3) | Sep 1 |
| Acme | Backend Intern | Seattle, WA | [Apply](https://jobs.example/4) | Sep 1 |
"""


def test_markdown_feed_reads_html_and_markdown_links_and_continuation_rows():
    jobs = github.parse_markdown(MARKDOWN, github.Board("x", "u", "markdown", hint_year=2027))
    assert [(j.company, j.title, j.url) for j in jobs] == [
        ("Shopify", "Software Engineering Intern", "https://jobs.example/1"),
        ("Shopify", "Security Intern", "https://jobs.example/2"),
    ]
    assert all(j.term == "summer-2027" for j in jobs)
    assert github._cell_link("[![Apply](https://img.shields.io/badge/a.svg)](https://jobs.example/3)") == "https://jobs.example/3"


def test_harvest_only_boards_contribute_postings_but_no_jobs(monkeypatch):
    monkeypatch.setattr(github, "get_text", lambda url, **kw: "see https://job-boards.greenhouse.io/acme/jobs/1 and https://github.com/x/y and https://img.shields.io/a.svg")
    res = github.scrape_board(github.Board("n", "u", "markdown", harvest_only=True))
    assert res.jobs == [] and [p.url for p in res.postings] == ["https://job-boards.greenhouse.io/acme/jobs/1"]


def test_all_boards_failing_is_an_error(monkeypatch):
    from internbot.sources.base import SourceError

    monkeypatch.setattr(github, "get_text", lambda *a, **k: (_ for _ in ()).throw(SourceError("x")))
    with pytest.raises(SourceError):
        github.scrape(boards=[github.Board("n", "u", "markdown")])


def test_jobbank_feed():
    xml = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Software Developer Intern</title>
      <link href="https://jobbank.gc.ca/1"/><summary type="html">&lt;strong&gt;Employer:&lt;/strong&gt; Acme Inc&lt;br&gt;&lt;strong&gt;Location:&lt;/strong&gt; Montréal (QC)</summary></entry>
      <entry><title>Software Developer Intern</title><link href="https://jobbank.gc.ca/2"/><summary>Location:&lt;/strong&gt; Regina (SK)</summary></entry></feed>"""
    jobs = jobbank.parse_feed(xml)
    assert [(j.company, j.location) for j in jobs] == [("Acme Inc", "Montréal, QC")]


def test_mines_levels_and_hn_for_apply_urls(monkeypatch):
    monkeypatch.setattr(levelsfyi, "get_json", lambda *a, **k: [{"link": "https://jobs.lever.co/a/1", "company": " A "}, {"link": "mailto:x"}, {"nolink": 1}])
    assert levelsfyi.scrape().postings == [Posting("https://jobs.lever.co/a/1", "A")]
    html = 'Apply <a href="https://jobs.lever.co/b/1">here</a> <a href="https://news.ycombinator.com/item?id=1">hn</a> <a href="https://x/y.png">img</a>'
    assert hnhiring.urls_in(html) == ["https://jobs.lever.co/b/1"]


def test_discovery_guesses_board_urls_the_harvesters_can_read():
    assert discover.slug_variants("1Password") == ["1password", "1Password"]
    assert discover.slug_variants("Lightspeed Commerce") == ["lightspeedcommerce", "lightspeed-commerce", "LightspeedCommerce"]
    posts = discover.guess_postings(["Hopper"])
    tokens = ats.harvest_tokens(posts)
    assert tokens["greenhouse"] == {"hopper": "Hopper", "Hopper": "Hopper"} and set(tokens["ashby"]) == {"hopper", "Hopper"}
    assert set(workable.harvest_tenants(posts)) == {"hopper", "Hopper"} and recruitee.harvest_tenants(posts) == {"hopper": "Hopper"}
    assert len(discover.load_employers()) > 50


def test_ashby_builds_jobs_with_pay(monkeypatch):
    from internbot.sources import ashby

    monkeypatch.setattr(ashby, "get_json", lambda *a, **k: {"jobs": [
        {"title": "Software Engineer Intern", "location": "Montreal", "jobUrl": "https://a/1", "descriptionPlain": "Winter 2027",
         "compensation": {"compensationTierSummary": "CA$40 - CA$50 / hr"}},
        {"title": "Software Engineer Intern", "location": "Montreal", "jobUrl": "https://a/2", "isListed": False}]}
    )
    jobs = ashby.fetch_jobs("acme", "Acme")
    assert len(jobs) == 1 and jobs[0].compensation == "CA$40 - CA$50 / hr" and jobs[0].term == "winter-2027"
