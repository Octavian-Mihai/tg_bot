"""Curated internship lists on GitHub (SimplifyJobs-style listings.json feeds and README tables).

They serve two purposes. Boards that are current are read as job sources. Every board, current
or stale, is also *mined*: its apply URLs name the employers' own ATS boards, which the ATS
scrapers then enumerate directly. A board can be worthless as a feed (last cycle's postings)
while still naming hundreds of employers whose boards carry this cycle's roles.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable

from internbot import places
from internbot.filters import is_wanted_title
from internbot.models import Job
from internbot.sources.base import FeedResult, Posting, SourceError, get_json, get_text, parallel_map
from internbot.sources.common import build_job
from internbot.terms import OTHER_CYCLE, term_for_season_field, term_for_source
from internbot.textutil import html_to_text

log = logging.getLogger(__name__)

_RAW = "https://raw.githubusercontent.com"


@dataclass(frozen=True)
class Board:
    name: str
    url: str
    type: str  # "listings" (JSON) | "markdown" (README table)
    harvest_only: bool = False  # mined for ATS tokens, contributes no jobs of its own
    hint_year: int | None = None  # the board is scoped to this cycle ("Summer2027-Internships")
    mapper: Callable[[object], list[dict]] | None = None  # normalises a non-standard JSON payload


def _zshah(raw: object) -> list[dict]:
    # keyed by id, with `company` instead of `company_name`
    return [{"url": j.get("url"), "company_name": j.get("company")} for j in (raw or {}).values()] if isinstance(raw, dict) else []


BOARDS = [
    Board("vanshb03/Summer2027-Internships", f"{_RAW}/vanshb03/Summer2027-Internships/dev/.github/scripts/listings.json", "listings", hint_year=2027),
    Board("speedyapply/2027-SWE-College-Jobs", f"{_RAW}/speedyapply/2027-SWE-College-Jobs/main/README.md", "markdown", hint_year=2027),
    Board("speedyapply/2027-AI-College-Jobs", f"{_RAW}/speedyapply/2027-AI-College-Jobs/main/README.md", "markdown", hint_year=2027),
    Board("sndsh404/summer-2027-internships", f"{_RAW}/sndsh404/summer-2027-internships/main/README.md", "markdown", hint_year=2027),
    # Current 2027-cycle boards that don't guarantee their term: each posting classifies from its own title.
    Board("zapplyjobs/Canada-Internships-2027", f"{_RAW}/zapplyjobs/Canada-Internships-2027/main/README.md", "markdown"),
    # speedyapply keeps non-US roles (including Montreal) in a separate file from the US list.
    Board("speedyapply/2027-SWE-College-Jobs (international)", f"{_RAW}/speedyapply/2027-SWE-College-Jobs/main/INTERN_INTL.md", "markdown", hint_year=2027),
    Board("speedyapply/2027-AI-College-Jobs (international)", f"{_RAW}/speedyapply/2027-AI-College-Jobs/main/INTERN_INTL.md", "markdown", hint_year=2027),
    Board("resumax/tech-internships", f"{_RAW}/resumax/tech-internships/main/README.md", "markdown"),
    # Token mines only. SimplifyJobs' ~15k postings name every employer that runs a summer program.
    Board("SimplifyJobs/New-Grad-Positions", f"{_RAW}/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json", "listings", harvest_only=True),
    Board("SimplifyJobs/Summer2026-Internships", f"{_RAW}/SimplifyJobs/Summer2026-Internships/dev/.github/scripts/listings.json", "listings", harvest_only=True),
    # Canadian boards: mostly Workday, which is why they matter. No Canadian employer is ever
    # queried otherwise (only 7 of 44 major Canadian tech firms appear in the US feeds).
    Board("negarprh/Canadian-Tech-Internships", f"{_RAW}/negarprh/Canadian-Tech-Internships-2026/main/README.md", "markdown", harvest_only=True),
    Board("hanzili/canada_sde_intern_position", f"{_RAW}/hanzili/canada_sde_intern_position/main/README.md", "markdown", harvest_only=True),
    Board("Dannny-Babs/Canadian-Tech-Internships", f"{_RAW}/Dannny-Babs/Canadian-Tech-Internships-2025/main/README.md", "markdown", harvest_only=True),
    Board("zapplyjobs/Internships-2027", f"{_RAW}/zapplyjobs/Internships-2027/main/README.md", "markdown", harvest_only=True),
    Board("perixtar/Summer-2027-Internships-Hourly-Update", f"{_RAW}/perixtar/Summer-2027-Internships-Hourly-Update/main/README.md", "markdown", harvest_only=True),
    Board("zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships",
          f"{_RAW}/zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships/main/data/jobs.json",
          "listings", harvest_only=True, mapper=_zshah),
]

# ---- JSON listings -------------------------------------------------------------------------------


def parse_listings(listings: list[dict], board: Board) -> list[Job]:
    jobs = []
    for l in listings:
        if not isinstance(l, dict) or l.get("active") is False or l.get("is_visible") is False:
            continue
        url = str(l.get("url") or "")
        if not url.startswith("http"):
            continue
        title = l.get("title") or ""
        term = None
        if board.hint_year is not None and l.get("season"):
            term = term_for_season_field(l["season"], board.hint_year)
            if term == OTHER_CYCLE:
                continue  # a Fall/Spring row on a Summer board
        elif board.hint_year is not None:
            term = term_for_source(board.hint_year, title)
        locations = l.get("locations")
        where = " ; ".join(x for x in (locations if isinstance(locations, list) else [locations]) if x)
        job = build_job(source="github", ident=url, company=l.get("company_name") or "Unknown", title=title,
                        location=where, url=url, term=term)
        if job:
            jobs.append(job)
    return jobs


# ---- markdown README tables ----------------------------------------------------------------------

_MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_BADGE = re.compile(r"img\.shields\.io|badgen\.net|\.(?:png|svg|gif|jpe?g)(?:$|\?)", re.I)
_HREF = re.compile(r"""<a\s[^>]*href=["']([^"']+)["']""", re.I)
_MD_URL = re.compile(r"\]\(\s*(https?://[^\s)]+)\s*\)")


def _cell_text(cell: str) -> str:
    """A cell's visible text. Cells mix HTML and markdown; collapse `**[Name](url)**` to `Name`."""
    return html_to_text(_MD_LINK.sub(r"\1", cell).replace("*", "").replace("`", ""))


def _cell_link(cell: str) -> str:
    """Apply links come as <a href>, [apply](url), or [![Apply](badge.svg)](url); the last nests
    the real link outermost, so it matches last and the badge image is skipped."""
    m = _HREF.search(cell)
    if m:
        return m.group(1)
    links = [u for u in _MD_URL.findall(cell) if not _BADGE.search(u)]
    return links[-1] if links else ""


def parse_markdown(markdown: str, board: Board) -> list[Job]:
    jobs: list[Job] = []
    cols: dict[str, int] | None = None
    last_company = ""
    for line in markdown.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = line.removeprefix("|").removesuffix("|").split("|")
        if all(re.fullmatch(r"[\s:-]*", c) for c in cells):
            continue
        texts = [c.strip() for c in cells]
        lower = [t.lower() for t in texts]
        if "company" in lower:
            def find(*names):
                return next((i for i, t in enumerate(lower) if any(n in t for n in names)), -1)
            cols = {"company": find("company"), "role": find("role", "position", "title"),
                    "location": find("location"), "link": find("link", "application", "posting", "apply")}
            continue
        if not cols or min(cols["company"], cols["role"], cols["link"]) < 0 or len(texts) <= max(cols.values()):
            continue
        company = _cell_text(texts[cols["company"]])
        if company in ("↳", ""):
            company = last_company
        else:
            last_company = company
        title = _cell_text(texts[cols["role"]])
        where = _cell_text(re.sub(r"<\s*/?\s*br\s*/?\s*>", ", ", texts[cols["location"]], flags=re.I)) if cols["location"] >= 0 else ""
        url = _cell_link(texts[cols["link"]]) or _cell_link(texts[cols["company"]])
        if not company or not title or not url.startswith("http"):
            continue
        term = term_for_source(board.hint_year, title) if board.hint_year is not None else None
        job = build_job(source="github", ident=url, company=company, title=title, location=where, url=url, term=term)
        if job:
            jobs.append(job)
    return jobs


_NOT_AN_APPLY_URL = re.compile(r"img\.shields\.io|badgen\.net|\.(?:png|svg|gif|jpe?g)(?:$|\?)|github\.com|githubusercontent\.com", re.I)


def _harvest_markdown_urls(markdown: str) -> list[Posting]:
    """A plain URL sweep: indifferent to how the link was written, which parse_markdown isn't."""
    return [Posting(u, "") for u in re.findall(r"https?://[^\s)\"'<>\]]+", markdown) if not _NOT_AN_APPLY_URL.search(u)]


# ---- driver --------------------------------------------------------------------------------------


def scrape_board(board: Board) -> FeedResult:
    if board.type == "listings":
        raw = get_json(board.url, timeout=60, retries=2)
        listings = board.mapper(raw) if board.mapper else raw
        if not isinstance(listings, list):
            raise SourceError("unexpected listings shape")
        # Every posting on the board, not just the ones we want: an apply URL for a Seattle PM
        # role still tells us that company's Greenhouse token, and its name labels the token.
        postings = [Posting(str(l["url"]), (l.get("company_name") or "").strip()) for l in listings if isinstance(l, dict) and l.get("url")]
        jobs = [] if board.harvest_only else parse_listings(listings, board)
    else:
        markdown = get_text(board.url, timeout=60, retries=2)
        if board.harvest_only:
            jobs, postings = [], _harvest_markdown_urls(markdown)
        else:
            jobs = parse_markdown(markdown, board)
            postings = [Posting(j.url, j.company) for j in jobs]
    log.info("GitHub %s: %s", board.name,
             f"token mine only, {len(postings)} apply URLs" if board.harvest_only else f"{len(jobs)} matching jobs")
    return FeedResult(jobs, postings)


def scrape(workers: int = 8, boards: list[Board] | None = None) -> FeedResult:
    boards = BOARDS if boards is None else boards
    results = parallel_map(boards, scrape_board, workers)
    jobs: list[Job] = []
    postings: list[Posting] = []
    failed = 0
    for board, res in zip(boards, results):
        if res is None:
            failed += 1
            log.warning("GitHub %s failed", board.name)
            continue
        jobs += res.jobs
        postings += res.postings
    if failed == len(boards):
        raise SourceError("every GitHub board failed")
    return FeedResult(jobs, postings)
