"""Workable boards (apply.workable.com/<tenant>). Two passes: the listing carries no description."""
from __future__ import annotations

import logging
import re
from typing import Iterable
from urllib.parse import quote

from internbot.models import Job
from internbot.sources.base import Posting, flatten, get_json, parallel_map, post_json
from internbot.sources.common import build_job, reclassify
from internbot.sources.harvest import first_segment, remember, urls
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)

API = "https://apply.workable.com/api"
MAX_PAGES = 10
_NOT_A_TENANT = re.compile(r"^(?:j|jobs|api|assets|embed|widget|backend|spa)$", re.I)
_NOT_A_SUBDOMAIN = re.compile(r"^(?:www|apply|api|help|support|status|blog|careers)$", re.I)


def harvest_tenants(postings: Iterable[Posting]) -> dict[str, str]:
    found: dict[str, str] = {}
    for u, company in urls(postings):
        host = u.hostname.lower()
        if host == "apply.workable.com":
            seg = first_segment(u.path)
            if seg and not _NOT_A_TENANT.match(seg):
                remember(found, seg, company)
        else:
            m = re.match(r"^([^.]+)\.workable\.com$", host)
            if m and not _NOT_A_SUBDOMAIN.match(m.group(1)):
                remember(found, m.group(1), company)
    return found


def _location(loc: dict | None, locations: list | None) -> str:
    parts = []
    for l in [loc, *(locations or [])]:
        if l:
            parts.append(", ".join(x for x in [l.get("city"), l.get("region"), l.get("country")] if x))
    return " ; ".join(p for p in parts if p)


def scrape_tenant(token: str, company: str) -> list[Job]:
    hits: list[tuple[Job, str]] = []
    cursor = None
    for _ in range(MAX_PAGES):
        body = {"query": "", **({"token": cursor} if cursor else {})}
        res = post_json(f"{API}/v3/accounts/{quote(token)}/jobs", body)
        for j in res.get("results") or []:
            if j.get("state") and j["state"] != "published":
                continue
            code = j.get("shortcode")
            if not code:
                continue
            url = f"https://apply.workable.com/{quote(token)}/j/{code}/"
            job = build_job(source="workable", ident=url, company=company or token, title=j.get("title") or "",
                            location=_location(j.get("location"), j.get("locations")), url=url)
            if job:
                hits.append((job, code))
        cursor = res.get("nextPage") or (res.get("paging") or {}).get("next")
        if not cursor:
            break

    def enrich(hit: tuple[Job, str]) -> Job | None:
        job, code = hit
        try:
            d = get_json(f"{API}/v2/accounts/{quote(token)}/jobs/{code}", headers={"Accept": "application/json"}, retries=1)
        except Exception:  # noqa: BLE001
            return job
        return reclassify(job, html_to_text(" ".join(filter(None, [d.get("description"), d.get("requirements"), d.get("benefits")]))))

    return [j for j in parallel_map(hits, enrich, workers=4) if j]


def scrape(postings: Iterable[Posting], workers: int, deadline: float | None) -> list[Job]:
    tenants = harvest_tenants(postings)
    if not tenants:
        return []
    log.info("Workable: enumerating %d tenant boards", len(tenants))
    jobs, reachable = flatten(parallel_map(list(tenants.items()), lambda t: scrape_tenant(*t), workers, deadline))
    log.info("Workable: %d/%d boards reachable, %d matching jobs", reachable, len(tenants), len(jobs))
    return jobs
