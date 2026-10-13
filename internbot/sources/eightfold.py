"""Eightfold career sites. Its API wants the employer's corporate domain (not the eightfold host),
guessed as `<tenant>.com` and overridable in data/eightfold-domains.json. It soft-blocks datacenter
IPs, so a block yields empty results, never wrong ones."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

from internbot.models import Job
from internbot.sources.base import Posting, flatten, get_json, parallel_map
from internbot.sources.common import build_job
from internbot.sources.harvest import urls
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)

PAGE = 50
MAX_PAGES = 5
DOMAINS_PATH = Path(__file__).resolve().parents[2] / "data" / "eightfold-domains.json"


def _overrides(path: Path = DOMAINS_PATH) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def harvest_sites(postings: Iterable[Posting], overrides: dict | None = None) -> dict[str, dict]:
    overrides = _overrides() if overrides is None else overrides
    sites: dict[str, dict] = {}
    for u, company in urls(postings):
        m = re.match(r"^([^.]+)\.eightfold\.ai$", u.hostname, re.I)
        if not m:
            continue
        host, tenant = u.hostname.lower(), m.group(1).lower()
        site = sites.setdefault(host, {"company": company, "domain": overrides.get(host) or overrides.get(tenant) or f"{tenant}.com"})
        if company and not site["company"]:
            site["company"] = company
    return sites


def scrape_site(host: str, company: str, domain: str) -> list[Job]:
    jobs: list[Job] = []
    total, page = float("inf"), 0
    while page * PAGE < total and page < MAX_PAGES:
        res = get_json(f"https://{host}/api/apply/v2/jobs", params={
            "domain": domain, "query": "intern", "sort_by": "relevance", "num": PAGE, "start": page * PAGE,
        }, headers={"Accept": "application/json"}, retries=1)
        total = res.get("count") or 0
        positions = res.get("positions") or []
        if not positions:
            break
        for p in positions:
            url = p.get("canonicalPositionUrl") or (f"https://{host}/careers/job/{quote(str(p['id']))}" if p.get("id") is not None else "")
            where = " ; ".join(x for x in [p.get("location"), *(p.get("locations") or [])] if isinstance(x, str) and x)
            job = build_job(source="eightfold", ident=url, company=company or host.split(".")[0], title=p.get("name") or "",
                            location=where, url=url, description=html_to_text(p.get("job_description") or p.get("description") or ""))
            if job:
                jobs.append(job)
        page += 1
    return jobs


def scrape(postings: Iterable[Posting], workers: int, deadline: float | None) -> list[Job]:
    sites = harvest_sites(postings)
    if not sites:
        return []
    log.info("Eightfold: enumerating %d employer sites", len(sites))
    work = [(h, s["company"], s["domain"]) for h, s in sites.items()]
    jobs, reachable = flatten(parallel_map(work, lambda w: scrape_site(*w), workers, deadline))
    log.info("Eightfold: %d/%d sites reachable, %d matching jobs", reachable, len(sites), len(jobs))
    return jobs
