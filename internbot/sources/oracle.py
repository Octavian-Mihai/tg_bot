"""Oracle Fusion (HCM) candidate-experience sites: Canadian banks and telcos run campus hiring here."""
from __future__ import annotations

import logging
import re
from typing import Iterable, NamedTuple
from urllib.parse import quote

from internbot import places
from internbot.filters import is_wanted_title
from internbot.models import Job
from internbot.sources.base import Posting, flatten, get_json, parallel_map
from internbot.sources.common import build_job, reclassify
from internbot.sources.harvest import remember
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)

PAGE = 200
MAX_PAGES = 5
_SITE_URL = re.compile(r"^https://([^/]+\.oraclecloud\.com)/.*/sites/([^/?#]+)", re.I)


class Site(NamedTuple):
    host: str
    site: str
    company: str = ""


def harvest_sites(postings: Iterable[Posting]) -> list[Site]:
    found: dict[tuple, str] = {}
    for p in postings:
        m = _SITE_URL.match(p.url or "")
        if m:
            remember(found, (m.group(1), m.group(2)), (p.company or "").strip())
    return [Site(*key, company) for key, company in found.items()]


def _list_url(s: Site, offset: int) -> str:
    return (
        f"https://{s.host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        f"?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber={quote(s.site)},"
        f"keyword=intern,limit={PAGE},offset={offset}"
    )


def _detail_url(s: Site, ident: str) -> str:
    return (
        f"https://{s.host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
        f"?expand=all&onlyData=true&finder=ById;Id=%22{quote(str(ident))}%22,siteNumber={quote(s.site)}"
    )


def _apply_url(s: Site, ident: str) -> str:
    return f"https://{s.host}/hcmUI/CandidateExperience/en/sites/{quote(s.site)}/job/{quote(str(ident))}"


def scrape_site(s: Site) -> list[Job]:
    hits: list[tuple[str, str, str]] = []
    total, offset = float("inf"), 0
    while offset < total and offset < MAX_PAGES * PAGE:
        items = get_json(_list_url(s, offset), retries=2).get("items") or [{}]
        box = items[0]
        reqs = box.get("requisitionList") or []
        total = box.get("TotalJobsCount") or 0
        if not reqs:
            break
        for r in reqs:
            where = r.get("PrimaryLocation") or ""
            if r.get("Id") and is_wanted_title(r.get("Title"), "internship") and places.in_area(where):
                hits.append((str(r["Id"]), r["Title"], where))
        offset += PAGE
    if not hits:
        return []

    def enrich(hit: tuple[str, str, str]) -> Job | None:
        ident, title, where = hit
        url = _apply_url(s, ident)
        job = build_job(source="oracle", ident=url, company=s.company or s.host.split(".")[0],
                        title=title, location=where, url=url)
        if job is None:
            return None
        try:
            item = (get_json(_detail_url(s, ident), retries=1).get("items") or [{}])[0]
        except Exception:  # noqa: BLE001
            return job
        text = " ".join(filter(None, [item.get("ExternalDescriptionStr"), item.get("ExternalResponsibilitiesStr"),
                                      item.get("ExternalQualificationsStr")]))
        return reclassify(job, html_to_text(text))

    return [j for j in parallel_map(hits, enrich, workers=4) if j]


def scrape(postings: Iterable[Posting], workers: int, deadline: float | None) -> list[Job]:
    sites = harvest_sites(postings)
    if not sites:
        return []
    log.info("Oracle: enumerating %d tenant sites", len(sites))
    jobs, reachable = flatten(parallel_map(sites, scrape_site, workers, deadline))
    log.info("Oracle: %d/%d sites reachable, %d matching jobs", reachable, len(sites), len(jobs))
    return jobs
