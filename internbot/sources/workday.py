"""Workday career sites (the ATS most Canadian employers use).

A tenant is found from any `<tenant>.wdN.myworkdayjobs.com/<site>` apply URL, then its public
`/wday/cxs/` API is searched for "intern". Many Canadian employers run a student-only campus site,
where a title needn't say "intern" to be one.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable, NamedTuple
from urllib.parse import quote

from internbot import places
from internbot.filters import is_wanted_title
from internbot.models import Job
from internbot.sources.base import Posting, flatten, get_json, parallel_map, post_json
from internbot.sources.common import build_job, reclassify
from internbot.sources.harvest import remember
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)

PAGE = 20
MAX_PAGES = 10

_TENANT_URL = re.compile(r"^https://([^./]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)", re.I)
# myworkdaysite.com puts the tenant in the path: /recruiting/<tenant>/<site>
_SITE_URL = re.compile(r"^https://(wd\d+)\.myworkdaysite\.com/(?:[a-z]{2}-[A-Z]{2}/)?recruiting/([^/?#]+)/([^/?#]+)", re.I)
_NOT_A_SITE = re.compile(r"^(job|jobs)$", re.I)

# Sites whose entire inventory is student roles. `intern` carries a lookahead rejecting the two
# words that swallow it: intern·al (`spgi_internal`) and intern·ational (`HUBInternational`).
_CAMPUS_SITE = re.compile(r"campus|student|intern(?!al|ational)|university|new[-_]?grad|early[-_ ]?career|graduate", re.I)


class Target(NamedTuple):
    tenant: str
    pod: str
    site: str
    domain: str  # myworkdayjobs | myworkdaysite
    company: str = ""


def _host(t: Target) -> str:
    return f"{t.pod}.myworkdaysite.com" if t.domain == "myworkdaysite" else f"{t.tenant}.{t.pod}.myworkdayjobs.com"


def _api(t: Target) -> str:
    return f"https://{_host(t)}/wday/cxs/{t.tenant}/{t.site}"


def job_url(t: Target, external_path: str) -> str:
    if t.domain == "myworkdaysite":
        return f"https://{_host(t)}/recruiting/{t.tenant}/{t.site}{external_path}"
    return f"https://{_host(t)}/{t.site}{external_path}"


def _parse(url: str) -> Target | None:
    m = _TENANT_URL.match(url)
    if m:
        return Target(m.group(1), m.group(2), m.group(3), "myworkdayjobs")
    m = _SITE_URL.match(url)
    if m:
        return Target(m.group(2), m.group(1), m.group(3), "myworkdaysite")
    return None


def harvest_targets(postings: Iterable[Posting]) -> list[Target]:
    found: dict[tuple, str] = {}
    for p in postings:
        t = _parse(p.url or "")
        if not t or _NOT_A_SITE.match(t.site):
            continue
        remember(found, t[:4], (p.company or "").strip())
    return [Target(*key, company) for key, company in found.items()]


def scrape_site(t: Target) -> list[Job]:
    kind = "campus" if _CAMPUS_SITE.search(t.site) else "internship"
    api = _api(t)
    hits: list[tuple[str, str, str]] = []
    total, offset = float("inf"), 0
    while offset < total and offset < MAX_PAGES * PAGE:
        page = post_json(f"{api}/jobs", {"appliedFacets": {}, "limit": PAGE, "offset": offset, "searchText": "intern"})
        total = page.get("total") or 0
        postings = page.get("jobPostings") or []
        if not postings:
            break
        for p in postings:
            where = p.get("locationsText") or ""
            if p.get("externalPath") and is_wanted_title(p.get("title"), kind) and places.in_area(where):
                hits.append((p["title"], where, p["externalPath"]))
        offset += PAGE
    if not hits:
        return []

    def enrich(hit: tuple[str, str, str]) -> Job | None:
        title, where, path = hit
        job = build_job(source="workday", ident=job_url(t, path), company=t.company or t.tenant,
                        title=title, location=where, url=job_url(t, path), kind=kind)
        if job is None:
            return None
        try:
            detail = get_json(f"{api}{quote(path, safe='/')}", headers={"Accept": "application/json"}, retries=1)
        except Exception:  # noqa: BLE001 - keep the job; the term just stays unstated
            return job
        return reclassify(job, html_to_text((detail.get("jobPostingInfo") or {}).get("jobDescription")))

    return [j for j in parallel_map(hits, enrich, workers=4) if j]


def scrape(postings: Iterable[Posting], workers: int, deadline: float | None) -> list[Job]:
    targets = harvest_targets(postings)
    if not targets:
        return []
    campus = sum(1 for t in targets if _CAMPUS_SITE.search(t.site))
    log.info("Workday: enumerating %d tenant sites (%d campus/student portals)", len(targets), campus)
    jobs, reachable = flatten(parallel_map(targets, scrape_site, workers, deadline))
    log.info("Workday: %d/%d sites reachable, %d matching jobs", reachable, len(targets), len(jobs))
    return jobs
