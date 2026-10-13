"""levels.fyi internship data: ~14k rows mined for apply-URL board tokens only (the rows are
salary datapoints, not postings)."""
from __future__ import annotations

import logging

from internbot.sources.base import FeedResult, Posting, SourceError, get_json

log = logging.getLogger(__name__)
URL = "https://www.levels.fyi/js/internshipData.json"


def scrape() -> FeedResult:
    data = get_json(URL, timeout=60, retries=2)
    if not isinstance(data, list):
        raise SourceError("unexpected levels.fyi shape")
    postings = [
        Posting(r["link"], (r.get("company") or "").strip())
        for r in data
        if isinstance(r, dict) and isinstance(r.get("link"), str) and r["link"].lower().startswith(("http://", "https://"))
    ]
    log.info("levels.fyi: token mine only, %d apply URLs from %d rows", len(postings), len(data))
    return FeedResult([], postings)
