"""Personio XML feeds (<tenant>.jobs.personio.de|com/xml). European-first, so it mostly fires on
employers that discovery turns up."""
from __future__ import annotations

import logging
import re
from typing import Iterable
from urllib.parse import quote

from defusedxml import ElementTree as ET

from internbot.models import Job
from internbot.sources.base import Posting, flatten, get_text, parallel_map
from internbot.sources.common import build_job
from internbot.sources.harvest import remember, urls
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)
_NOT_A_TENANT = re.compile(r"^(?:www|api|help|support|status|blog|jobs)$", re.I)


def harvest_tenants(postings: Iterable[Posting]) -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for u, company in urls(postings):
        m = re.match(r"^([^.]+)\.jobs\.personio\.(?:de|com)$", u.hostname, re.I)
        if m and not _NOT_A_TENANT.match(m.group(1)):
            token = m.group(1).lower()
            tld = "com" if u.hostname.lower().endswith(".com") else "de"
            if token not in found or (company and not found[token][0]):
                found[token] = (company or (found.get(token) or ("", ""))[0], tld)
    return found


def _text(el, tag: str) -> str:
    child = el.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def scrape_tenant(token: str, company: str, tld: str) -> list[Job]:
    host = f"{token}.jobs.personio.{tld}"
    root = ET.fromstring(get_text(f"https://{host}/xml", headers={"Accept": "application/xml, text/xml"}))
    jobs = []
    for pos in root.iter("position"):
        ident, title = _text(pos, "id"), _text(pos, "name")
        if not ident or not title:
            continue
        offices = [_text(pos, "office")]
        extra = pos.find("additionalOffices")
        if extra is not None:
            offices += [(o.text or "").strip() for o in extra.findall("office")]
        description = html_to_text(" ".join((v.text or "") for v in pos.iter("value")))
        url = f"https://{host}/job/{quote(ident)}"
        job = build_job(source="personio", ident=url, company=company or token, title=title,
                        location=" ; ".join(dict.fromkeys(o for o in offices if o)), url=url, description=description)
        if job:
            jobs.append(job)
    return jobs


def scrape(postings: Iterable[Posting], workers: int, deadline: float | None) -> list[Job]:
    tenants = harvest_tenants(postings)
    if not tenants:
        return []
    log.info("Personio: enumerating %d tenant feeds", len(tenants))
    work = [(t, c, tld) for t, (c, tld) in tenants.items()]
    jobs, reachable = flatten(parallel_map(work, lambda w: scrape_tenant(*w), workers, deadline))
    log.info("Personio: %d/%d feeds reachable, %d matching jobs", reachable, len(tenants), len(jobs))
    return jobs
