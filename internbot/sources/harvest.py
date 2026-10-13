"""Shared helpers for turning apply URLs into ATS board tokens.

Every scraper that enumerates a company board starts from URLs some job feed already gave us.
The first non-empty company name wins; a later URL without one must not erase it.
"""
from __future__ import annotations

from typing import Iterable
from urllib.parse import unquote, urlparse

from internbot.sources.base import Posting


def parse(url: str):
    try:
        u = urlparse(url)
    except ValueError:
        return None
    return u if u.scheme in ("http", "https") and u.hostname else None


def first_segment(path: str) -> str | None:
    seg = next((s for s in path.split("/") if s), None)
    return unquote(seg) if seg else None


def remember(mapping: dict, key, company: str) -> None:
    if not mapping.get(key):
        mapping[key] = company


def urls(postings: Iterable[Posting]):
    """Yield (parsed_url, company) for every posting with a usable URL."""
    for p in postings:
        u = parse(p.url) if p.url else None
        if u:
            yield u, (p.company or "").strip()
