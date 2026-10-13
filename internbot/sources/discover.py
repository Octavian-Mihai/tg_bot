"""Guess company boards nobody has told us about.

Every board we enumerate is one some feed already named, which is circular: an employer absent
from the feeds is never queried. A company's board slug is almost always its name with the
punctuation removed, and the APIs answer on a deterministic URL, so a wrong guess is one cheap 404.

Instead of a second pipeline this emits *canonical apply URLs* for each guess. The harvesters
already parse a board token out of exactly that shape, so a guessed employer flows through the
same scrapers, dedupe and term gate. The URLs are never fetched; only their token is read.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from internbot.sources.base import Posting

log = logging.getLogger(__name__)

EMPLOYERS_PATH = Path(__file__).resolve().parents[2] / "data" / "employers.json"

_TEMPLATES = (
    "https://job-boards.greenhouse.io/{s}/jobs/0",
    "https://jobs.lever.co/{s}/0",
    "https://jobs.ashbyhq.com/{s}/0",
    "https://jobs.smartrecruiters.com/{s}/0",
    "https://apply.workable.com/{s}/",
    "https://{s}.recruitee.com/",
    "https://{s}.bamboohr.com/careers",
)
# iCIMS, Eightfold, Personio and Phenom are left out: their hostnames don't follow a guessable
# slug pattern, so a probe would 404 for every employer regardless.


def slug_variants(name: str) -> list[str]:
    """"1Password" runs `1password`, Faire runs `faire`, NBCUniversal runs `NBCUniversal3`: cover
    the cheap variants and let the 404s fall where they may."""
    trimmed = (name or "").strip()
    if not trimmed:
        return []
    lower = trimmed.lower()
    variants = [re.sub(r"[^a-z0-9]", "", lower), re.sub(r"[^a-z0-9]+", "-", lower).strip("-"), re.sub(r"[^A-Za-z0-9]", "", trimmed)]
    return [v for v in dict.fromkeys(variants) if v]


def load_employers(path: Path = EMPLOYERS_PATH) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []  # no list, no discovery: not an error
    employers = data.get("employers") if isinstance(data, dict) else data
    return [e for e in employers or [] if isinstance(e, str)]


def guess_postings(employers: list[str] | None = None) -> list[Posting]:
    employers = load_employers() if employers is None else employers
    postings = [Posting(t.format(s=slug), name) for name in employers for slug in slug_variants(name) for t in _TEMPLATES]
    if postings:
        log.info("Discovery: %d employers -> %d candidate boards to probe", len(employers), len(postings))
    return postings
