"""Hacker News "Who is hiring?": the monthly thread mined for apply URLs in its comments (the prose
is too irregular to parse into structured jobs)."""
from __future__ import annotations

import logging
import re
from html import unescape
from urllib.parse import urlparse

from internbot.sources.base import FeedResult, Posting, SourceError, get_json

log = logging.getLogger(__name__)

SEARCH = "https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring&query=hiring&hitsPerPage=10"
ITEM = "https://hn.algolia.com/api/v1/items/{id}"
_BLOCK_HOST = re.compile(r"(^|\.)(news\.ycombinator\.com|ycombinator\.com|algolia\.com|img\.shields\.io|badgen\.net)$", re.I)
_IMAGE = re.compile(r"\.(?:png|svg|gif|jpe?g)(?:$|\?)", re.I)
_HREF = re.compile(r"""href=["'](https?://[^"']+)["']""", re.I)


def urls_in(html: str) -> list[str]:
    out = []
    # HN escapes its hrefs ("https:&#x2F;&#x2F;..."), so decode before matching.
    for href in _HREF.findall(unescape(html or "")):
        host = urlparse(href).hostname or ""
        if host and not _IMAGE.search(href) and not _BLOCK_HOST.search(host):
            out.append(href)
    return out


def scrape() -> FeedResult:
    hits = get_json(SEARCH, retries=2).get("hits") or []
    story = next((h for h in hits if re.search(r"who is hiring", h.get("title") or "", re.I)), None)
    if not story:
        return FeedResult([], [])
    tree = get_json(ITEM.format(id=story["objectID"]), timeout=60, retries=2)
    seen: set[str] = set()
    postings = []
    for child in tree.get("children") or []:
        for url in urls_in(child.get("text") or ""):
            if url not in seen:
                seen.add(url)
                postings.append(Posting(url, ""))  # the name isn't reliably parseable from prose
    log.info('HN "%s": token mine only, %d apply URLs from %d comments', story.get("title"), len(postings), len(tree.get("children") or []))
    return FeedResult([], postings)
