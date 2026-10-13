"""iCIMS career sites. No JSON API: page the hosted search HTML for job links, then read each
job page's schema.org JobPosting."""
from __future__ import annotations

import json
import logging
import re
from typing import Iterable
from urllib.parse import unquote

from internbot.filters import is_wanted_title
from internbot.models import Job
from internbot.sources.base import Posting, flatten, get_text, parallel_map
from internbot.sources.common import build_job
from internbot.sources.harvest import remember, urls
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)

MAX_PAGES = 15
_VENDOR_HOST = re.compile(r"^(?:www|login|configure|secure|hire|internal|admin|api)\.icims\.com$", re.I)
_JOB_LINK = re.compile(r"/jobs/(\d+)/([^/\"?]+)/(?:login|job)", re.I)
_LD_JSON = re.compile(r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>([\s\S]*?)</script>", re.I)


def harvest_sites(postings: Iterable[Posting]) -> dict[str, str]:
    found: dict[str, str] = {}
    for u, company in urls(postings):
        host = u.hostname.lower()
        if host.endswith(".icims.com") and not _VENDOR_HOST.match(host):
            remember(found, host, company)
    return found


def _slug_to_title(slug: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"-+", " ", unquote(slug))).strip()


def _job_posting_ld(html: str) -> dict | None:
    for block in _LD_JSON.findall(html):
        try:
            data = json.loads(block.strip())
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict):
                kind = item.get("@type")
                if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
                    return item
    return None


def _ld_location(ld: dict) -> str:
    places_ = ld.get("jobLocation")
    places_ = places_ if isinstance(places_, list) else [places_] if places_ else []
    out = []
    for p in places_:
        a = (p or {}).get("address") or {}
        out.append(", ".join(x for x in [a.get("addressLocality"), a.get("addressRegion"), a.get("addressCountry")] if isinstance(x, str) and x))
    return " ; ".join(o for o in out if o)


def scrape_site(host: str, company: str) -> list[Job]:
    found: dict[str, str] = {}
    for pr in range(MAX_PAGES):
        try:
            html = get_text(f"https://{host}/jobs/search", params={"ss": 1, "pr": pr, "in_iframe": 1, "searchKeyword": "intern"})
        except Exception:  # noqa: BLE001 - a dead page ends paging rather than losing the site
            break
        added = 0
        for ident, slug in _JOB_LINK.findall(html):
            if ident not in found:
                found[ident] = slug
                added += 1
        if not added:
            break
    candidates = [(i, s) for i, s in found.items() if is_wanted_title(_slug_to_title(s), "internship")]

    def fetch(item: tuple[str, str]) -> Job | None:
        ident, slug = item
        url = f"https://{host}/jobs/{ident}/{slug}/job"
        try:
            ld = _job_posting_ld(get_text(url, params={"in_iframe": 1}))
        except Exception:  # noqa: BLE001 - no reliable title/location without the page
            return None
        if not ld or not ld.get("title"):
            return None
        org = ld.get("hiringOrganization")
        return build_job(source="icims", ident=url, company=company or (org.get("name") if isinstance(org, dict) else "") or host,
                         title=ld["title"], location=_ld_location(ld), url=url, description=html_to_text(ld.get("description")))

    return [j for j in parallel_map(candidates, fetch, workers=4) if j]


def scrape(postings: Iterable[Posting], workers: int, deadline: float | None) -> list[Job]:
    sites = harvest_sites(postings)
    if not sites:
        return []
    log.info("iCIMS: enumerating %d employer sites", len(sites))
    jobs, reachable = flatten(parallel_map(list(sites.items()), lambda s: scrape_site(*s), workers, deadline))
    log.info("iCIMS: %d/%d sites reachable, %d matching jobs", reachable, len(sites), len(jobs))
    return jobs
