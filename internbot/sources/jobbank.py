"""Canada Job Bank, the government feed, scoped by software NOC occupation codes.

21231 software developers, 21232 software engineers/designers, 21233 web designers/developers,
21234 web developers/programmers, 21211 data scientists. (The `term` query is ignored by the feed,
so the NOC filter is what scopes it.)
"""
from __future__ import annotations

import logging
import re

from defusedxml import ElementTree as ET

from internbot.models import Job
from internbot.sources.base import FeedResult, SourceError, get_text
from internbot.sources.common import build_job

log = logging.getLogger(__name__)

FEED = "https://www.jobbank.gc.ca/jobsearch/feed/jobSearchRSSfeed"
NOC_CODES = ("21231", "21232", "21233", "21234", "21211")


def _field(summary: str, label: str) -> str:
    m = re.search(rf"{label}:</strong>\s*([^<]+)", summary or "", re.I)
    return m.group(1).strip() if m else ""


def parse_feed(xml: str) -> list[Job]:
    root = ET.fromstring(xml)
    jobs = []
    for entry in (e for e in root.iter() if e.tag.split("}")[-1] == "entry"):
        def child(tag: str):
            return next((c for c in entry if c.tag.split("}")[-1] == tag), None)
        title = (child("title").text or "").strip() if child("title") is not None else ""
        link = child("link")
        url = link.get("href") if link is not None else ""
        summary = (child("summary").text or "") if child("summary") is not None else ""
        where = re.sub(r"\s*\(([A-Za-z]{2})\)\s*$", r", \1", _field(summary, "Location"))
        job = build_job(source="jobbank", ident=url or "", company=_field(summary, "Employer") or "Unknown",
                        title=title, location=where, url=url or "")
        if job:
            jobs.append(job)
    return jobs


def _queries() -> list[str]:
    noc = "&".join(f"fn21={c}" for c in NOC_CODES)
    # Quebec only: the feed is the newest 100 postings, and nationwide those are never Montreal.
    return [f"{noc}&fprov=QC", "searchstring=software+intern&fprov=QC", "searchstring=stagiaire+informatique&fprov=QC"]


def scrape() -> FeedResult:
    jobs: dict[str, Job] = {}
    failures = 0
    for query in _queries():
        try:
            xml = get_text(f"{FEED}?{query}&sort=D&rows=100", headers={"Accept": "application/atom+xml, application/xml"}, retries=2)
            for job in parse_feed(xml):
                jobs.setdefault(job.url, job)
        except Exception:  # noqa: BLE001
            failures += 1
    if failures == len(_queries()):
        raise SourceError("Job Bank feed failed")
    log.info("Job Bank: %d matching Canadian postings", len(jobs))
    return FeedResult(list(jobs.values()), [])  # apply URLs are jobbank.gc.ca pages, not ATS boards
