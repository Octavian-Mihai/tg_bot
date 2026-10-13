"""BambooHR career pages (<tenant>.bamboohr.com/careers): list, then a detail fetch per survivor."""
from __future__ import annotations

import logging
import re
from typing import Iterable
from urllib.parse import quote

from internbot.models import Job
from internbot.sources.base import Posting, flatten, get_json, parallel_map
from internbot.sources.common import build_job, reclassify
from internbot.sources.harvest import remember, urls
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)
_NOT_A_TENANT = re.compile(r"^(?:www|api|help|support|status|blog)$", re.I)
_JSON = {"Accept": "application/json"}


def harvest_tenants(postings: Iterable[Posting]) -> dict[str, str]:
    found: dict[str, str] = {}
    for u, company in urls(postings):
        m = re.match(r"^([^.]+)\.bamboohr\.com$", u.hostname, re.I)
        if m and not _NOT_A_TENANT.match(m.group(1)):
            remember(found, m.group(1).lower(), company)
    return found


def _location(j: dict) -> str:
    l, a = j.get("location") or {}, j.get("atsLocation") or {}
    bits = [l.get("city") or a.get("city"), l.get("state") or a.get("state") or a.get("province"), a.get("country")]
    text = ", ".join(dict.fromkeys(b for b in bits if b))
    return "Remote" if j.get("isRemote") and not text else text


def scrape_tenant(token: str, company: str) -> list[Job]:
    base = f"https://{quote(token)}.bamboohr.com/careers"
    result = get_json(f"{base}/list", headers=_JSON, retries=2).get("result") or []
    hits = []
    for j in result:
        if not j.get("id"):
            continue
        url = f"{base}/{quote(str(j['id']))}"
        job = build_job(source="bamboohr", ident=url, company=company or token,
                        title=j.get("jobOpeningName") or "", location=_location(j), url=url)
        if job:
            hits.append((job, j["id"]))

    def enrich(hit: tuple[Job, object]) -> Job | None:
        job, ident = hit
        try:
            opening = (get_json(f"{base}/{quote(str(ident))}/detail", headers=_JSON, retries=1).get("result") or {}).get("jobOpening") or {}
        except Exception:  # noqa: BLE001
            return job
        return reclassify(job, html_to_text(opening.get("description")))

    return [j for j in parallel_map(hits, enrich, workers=4) if j]


def scrape(postings: Iterable[Posting], workers: int, deadline: float | None) -> list[Job]:
    tenants = harvest_tenants(postings)
    if not tenants:
        return []
    log.info("BambooHR: enumerating %d tenant boards", len(tenants))
    jobs, reachable = flatten(parallel_map(list(tenants.items()), lambda t: scrape_tenant(*t), workers, deadline))
    log.info("BambooHR: %d/%d boards reachable, %d matching jobs", reachable, len(tenants), len(jobs))
    return jobs
