"""Recruitee boards (<tenant>.recruitee.com): one pass, the offers feed carries the description."""
from __future__ import annotations

import logging
import re
from typing import Iterable

from internbot.models import Job
from internbot.sources.base import Posting, flatten, get_json, parallel_map
from internbot.sources.common import build_job
from internbot.sources.harvest import remember, urls
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)
_NOT_A_TENANT = re.compile(r"^(?:www|api|help|support|status|blog|jobs|careers)$", re.I)


def harvest_tenants(postings: Iterable[Posting]) -> dict[str, str]:
    found: dict[str, str] = {}
    for u, company in urls(postings):
        m = re.match(r"^([^.]+)\.recruitee\.com$", u.hostname, re.I)
        if m and not _NOT_A_TENANT.match(m.group(1)):
            remember(found, m.group(1).lower(), company)
    return found


def _location(o: dict) -> str:
    parts = [", ".join(x for x in [o.get("city"), o.get("country")] if x)]
    for l in o.get("locations") or []:
        parts.append(l if isinstance(l, str) else ", ".join(x for x in [(l or {}).get("city"), (l or {}).get("country")] if x))
    return " ; ".join(p for p in parts if p) or o.get("location") or ""


def scrape_tenant(token: str, company: str) -> list[Job]:
    offers = get_json(f"https://{token}.recruitee.com/api/offers/", retries=2).get("offers") or []
    jobs = []
    for o in offers:
        if o.get("status") and o["status"] != "published":
            continue
        url = o.get("careers_apply_url") or o.get("careers_url") or f"https://{token}.recruitee.com/o/{o.get('slug') or o.get('id')}"
        job = build_job(
            source="recruitee", ident=url, company=company or o.get("company_name") or token,
            title=o.get("title") or "", location=_location(o), url=url, posted=o.get("published_at"),
            description=html_to_text(" ".join(filter(None, [o.get("description"), o.get("requirements")]))),
        )
        if job:
            jobs.append(job)
    return jobs


def scrape(postings: Iterable[Posting], workers: int, deadline: float | None) -> list[Job]:
    tenants = harvest_tenants(postings)
    if not tenants:
        return []
    log.info("Recruitee: enumerating %d tenant boards", len(tenants))
    jobs, reachable = flatten(parallel_map(list(tenants.items()), lambda t: scrape_tenant(*t), workers, deadline))
    log.info("Recruitee: %d/%d boards reachable, %d matching jobs", reachable, len(tenants), len(jobs))
    return jobs
