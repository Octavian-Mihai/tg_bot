"""Enumerates company boards on Greenhouse, Ashby and Lever from harvested apply URLs.

The curated GitHub lists are slices of these same boards, so they lag by days and omit plenty.
But their apply URLs hand us the board tokens for free: `job-boards.greenhouse.io/figureai/jobs/1`
means Figure AI's board is `figureai`, and the board API lists everything on it. All three APIs
are public and need no key.
"""
from __future__ import annotations

import logging
import re
from typing import Callable, Iterable

from internbot.models import Job
from internbot.sources import ashby, greenhouse, lever
from internbot.sources.base import Posting, flatten, parallel_map
from internbot.sources.harvest import first_segment, remember, urls

log = logging.getLogger(__name__)

FETCHERS: dict[str, Callable[[str, str], list[Job]]] = {
    "greenhouse": greenhouse.fetch_jobs,
    "ashby": ashby.fetch_jobs,
    "lever": lever.fetch_jobs,
}
_HOSTS = {
    "greenhouse": re.compile(r"(^|\.)(greenhouse\.io|grnh\.se)$", re.I),
    "ashby": re.compile(r"(^|\.)ashbyhq\.com$", re.I),
    "lever": re.compile(r"(^|\.)lever\.co$", re.I),
}
# Vendor demo boards carry fake postings ("leverdemo" lists an "Engineering Intern"). Anchored,
# so real companies whose names merely contain these words survive: Demodesk, demandbase.
_DEMO_BOARD = re.compile(
    r"^(?:lever|greenhouse|ashby)?(?:demo|test|sandbox|example|staging)$|"
    r"(^|[-_])(?:demo|test|sandbox|example|staging)([-_]|$)", re.I)


def _token(u, ats: str) -> str | None:
    if ats == "greenhouse":
        if re.search(r"(^|\.)grnh\.se$", u.hostname, re.I):
            return None  # a shortlink hash, not a board
        seg = first_segment(u.path)
        if seg == "embed":  # job-boards.greenhouse.io/embed/job_app?for=point72
            from urllib.parse import parse_qs

            return (parse_qs(u.query).get("for") or [None])[0]
        return seg
    return first_segment(u.path)


def harvest_tokens(postings: Iterable[Posting]) -> dict[str, dict[str, str]]:
    """{ats: {board token: company display name}} from apply URLs."""
    tokens: dict[str, dict[str, str]] = {a: {} for a in FETCHERS}
    for u, company in urls(postings):
        ats = next((a for a, host in _HOSTS.items() if host.search(u.hostname)), None)
        if not ats:
            continue
        token = _token(u, ats)
        if token and not _DEMO_BOARD.match(token):
            remember(tokens[ats], token, company)
    return tokens


def scrape(
    postings: Iterable[Posting],
    enabled: set[str],
    workers: int,
    deadline: float | None,
    skip: set[tuple[str, str]] = frozenset(),
) -> list[Job]:
    """Scrape every harvested board of the enabled ATSs. `skip` holds (ats, token) pairs already
    covered elsewhere (the hand-written companies.toml boards)."""
    tokens = harvest_tokens(postings)
    work = [
        (ats, token, company)
        for ats, mapping in tokens.items() if ats in enabled
        for token, company in mapping.items() if (ats, token.lower()) not in skip
    ]
    if not work:
        return []
    log.info("ATS: enumerating %d company boards (%s)", len(work),
             ", ".join(f"{len(m)} {a}" for a, m in tokens.items() if a in enabled))
    results = parallel_map(work, lambda w: FETCHERS[w[0]](w[1], w[2]), workers, deadline)
    jobs, reachable = flatten(results)
    log.info("ATS: %d/%d boards reachable, %d matching jobs", reachable, len(work), len(jobs))
    return jobs
