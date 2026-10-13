"""SmartRecruiters company boards (public API, no keyword filter, so every posting is paged)."""
from __future__ import annotations

import logging
import re
from typing import Iterable
from urllib.parse import quote, unquote

from internbot import places
from internbot.filters import is_wanted_title
from internbot.models import Job
from internbot.sources.base import Posting, flatten, get_json, parallel_map
from internbot.sources.common import build_job, reclassify
from internbot.sources.harvest import remember
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)

PAGE = 100
MAX_PAGES = 5
API = "https://api.smartrecruiters.com/v1/companies"
_COMPANY_URL = re.compile(r"^https://(?:jobs|careers)\.smartrecruiters\.com/([^/?#]+)", re.I)
_NOT_A_COMPANY = re.compile(r"^(one[-_]?click|apply|login|search|jobs)(?:[-_]|$)", re.I)


def harvest_companies(postings: Iterable[Posting]) -> dict[str, str]:
    found: dict[str, str] = {}
    for p in postings:
        m = _COMPANY_URL.match(p.url or "")
        if not m:
            continue
        token = unquote(m.group(1))
        if not _NOT_A_COMPANY.match(token):
            remember(found, token, (p.company or "").strip())
    return found


def scrape_company(token: str, name: str) -> list[Job]:
    hits: list[tuple[str, str, str]] = []
    total, offset = float("inf"), 0
    while offset < total and offset < MAX_PAGES * PAGE:
        page = get_json(f"{API}/{quote(token)}/postings", params={"limit": PAGE, "offset": offset}, retries=2)
        total = page.get("totalFound") or 0
        content = page.get("content") or []
        if not content:
            break
        for p in content:
            loc = p.get("location") or {}
            where = ", ".join(x for x in [loc.get("city"), loc.get("region"), loc.get("country")] if x)
            if p.get("id") and is_wanted_title(p.get("name"), "internship") and places.in_area(where):
                hits.append((p["id"], p["name"], where))
        offset += PAGE
    if not hits:
        return []

    def enrich(hit: tuple[str, str, str]) -> Job | None:
        ident, title, where = hit
        url = f"https://jobs.smartrecruiters.com/{quote(token)}/{quote(ident)}"
        description = ""
        try:
            detail = get_json(f"{API}/{quote(token)}/postings/{quote(ident)}", retries=1)
            sections = (detail.get("jobAd") or {}).get("sections") or {}
            description = html_to_text(" ".join(filter(None, [
                (sections.get("jobDescription") or {}).get("text"), (sections.get("qualifications") or {}).get("text")])))
            url = detail.get("applyUrl") or url
        except Exception:  # noqa: BLE001 - keep the constructed URL
            pass
        return build_job(source="smartrecruiters", ident=url, company=name or token, title=title,
                         location=where, url=url, description=description)

    return [j for j in parallel_map(hits, enrich, workers=4) if j]


def scrape(postings: Iterable[Posting], workers: int, deadline: float | None) -> list[Job]:
    companies = harvest_companies(postings)
    if not companies:
        return []
    log.info("SmartRecruiters: enumerating %d company boards", len(companies))
    jobs, reachable = flatten(parallel_map(list(companies.items()), lambda c: scrape_company(*c), workers, deadline))
    log.info("SmartRecruiters: %d/%d boards reachable, %d matching jobs", reachable, len(companies), len(jobs))
    return jobs
