"""Phenom People career sites: the Canadian banks and telcos. Each employer has a vanity domain,
so nothing can be harvested; the sites are listed in data/phenom-sites.json."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from urllib.parse import quote

from internbot.models import Job
from internbot.sources.base import flatten, parallel_map, post_json
from internbot.sources.common import build_job
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)

PAGE = 20
MAX_PAGES = 10
SITES_PATH = Path(__file__).resolve().parents[2] / "data" / "phenom-sites.json"


def load_sites(path: Path = SITES_PATH) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []  # no list, no Phenom scraping: not an error
    sites = data if isinstance(data, list) else data.get("sites", [])
    return [({"host": s} if isinstance(s, str) else s) for s in sites if s and (isinstance(s, str) or s.get("host"))]


def _body(site: dict, start: int) -> dict:
    return {
        "lang": site.get("lang", "en_us"), "deviceType": "desktop", "country": site.get("country", "us"),
        "ddoKey": "refineSearch", "sortBy": "", "subsearch": "", "from": start, "jobs": True, "counts": True,
        "all_fields": ["category", "country", "state", "city"], "size": PAGE, "clearAll": False,
        "jdsource": "facets", "isSliderEnable": False, "pageName": "search-results", "keywords": "intern",
        "global": True, "selected_fields": {}, "locationData": {},
    }


def scrape_site(site: dict) -> list[Job]:
    host, company = site["host"], site.get("company", "")
    jobs: list[Job] = []
    total, start = float("inf"), 0
    while start < total and start < MAX_PAGES * PAGE:
        refine = (post_json(f"https://{host}/widgets", _body(site, start)).get("refineSearch")) or {}
        total = refine.get("totalHits") or 0
        listing = (refine.get("data") or {}).get("jobs") or []
        if not listing:
            break
        for j in listing:
            ident = j.get("jobSeqNo") or j.get("jobId")
            if not ident:
                continue
            where = str(j.get("location") or ", ".join(x for x in [j.get("city"), j.get("state"), j.get("country")] if x))
            url = f"https://{host}/job/{quote(str(ident))}"
            job = build_job(source="phenom", ident=url, company=company or j.get("department") or host, title=j.get("title") or "",
                            location=where, url=url, description=html_to_text(j.get("description") or j.get("descriptionTeaser") or ""))
            if job:
                jobs.append(job)
        start += PAGE
    return jobs


def scrape(workers: int, deadline: float | None, sites: list[dict] | None = None) -> list[Job]:
    sites = load_sites() if sites is None else sites
    if not sites:
        return []
    log.info("Phenom: enumerating %d employer sites", len(sites))
    jobs, reachable = flatten(parallel_map(sites, scrape_site, workers, deadline))
    log.info("Phenom: %d/%d sites reachable, %d matching jobs", reachable, len(sites), len(jobs))
    return jobs
