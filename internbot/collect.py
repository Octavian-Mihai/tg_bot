"""Runs every enabled source and returns the postings they found.

Phase 1 reads the feeds (curated GitHub lists, Job Bank, The Muse, Adzuna, levels.fyi, HN). Each
returns jobs of its own plus *postings*: apply URLs that name employers' ATS boards.
Phase 2 enumerates those boards directly (Greenhouse, Ashby, Lever, Workday, Oracle,
SmartRecruiters, Workable, Recruitee, BambooHR, iCIMS, Eightfold, Personio, Phenom), plus the
boards guessed from data/employers.json.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Callable

from internbot.config import Config
from internbot.models import Job
from internbot.sources import (
    adzuna, ats, bamboohr, discover, eightfold, github, greenhouse, hnhiring, icims, jobbank,
    lever, levelsfyi, oracle, personio, phenom, recruitee, smartrecruiters, themuse, workable, workday,
)
from internbot.sources.base import FeedResult, Posting, SourceError, parallel_map

log = logging.getLogger(__name__)

ATS_FETCHERS = {"greenhouse": greenhouse.fetch_jobs, "lever": lever.fetch_jobs}


@dataclass
class Collected:
    jobs: list[Job] = field(default_factory=list)
    ok: int = 0
    failed: int = 0
    failed_names: list[str] = field(default_factory=list)
    by_source: dict[str, int] = field(default_factory=dict)


def _company_boards(config: Config) -> tuple[list[Job], int, list[str]]:
    results = parallel_map(
        config.companies,
        lambda c: ATS_FETCHERS[c.ats](c.slug, c.name),
        workers=config.settings.concurrency,
    )
    jobs: list[Job] = []
    failed: list[str] = []
    for company, res in zip(config.companies, results):
        if res is None:
            log.warning("source %s/%s failed", company.ats, company.slug)
            failed.append(f"{company.ats}/{company.slug}")
        else:
            jobs += res
    return jobs, len(config.companies) - len(failed), failed


def _run_feeds(settings) -> tuple[dict[str, FeedResult], list[str]]:
    feeds: dict[str, Callable[[], FeedResult]] = {
        "github": lambda: github.scrape(),
        "jobbank": jobbank.scrape,
        "themuse": themuse.scrape,
        "adzuna": lambda: FeedResult(adzuna.fetch_from_env(), []),
        "levelsfyi": levelsfyi.scrape,
        "hnhiring": hnhiring.scrape,
    }
    names = [n for n in feeds if n in settings.sources]
    outcomes: dict[str, FeedResult | Exception] = {}

    def run(name: str):
        try:
            return feeds[name]()
        except Exception as exc:  # noqa: BLE001 - one dead feed must not stop the rest
            return exc

    for name, out in zip(names, parallel_map(names, run, workers=len(names) or 1)):
        outcomes[name] = out if out is not None else SourceError("did not finish")
    ok = {n: o for n, o in outcomes.items() if isinstance(o, FeedResult)}
    for name, out in outcomes.items():
        if not isinstance(out, FeedResult):
            log.warning("source %s failed: %s", name, out if isinstance(out, SourceError) else type(out).__name__)
    return ok, [n for n in names if n not in ok]


def collect(config: Config) -> Collected:
    """Fetch from every enabled source. One failing source never stops the others. Direct
    company boards come first so they win over aggregators when the same posting appears twice."""
    s = config.settings
    out = Collected()
    deadline = time.monotonic() + s.time_budget_minutes * 60
    workers = s.concurrency

    board_jobs, board_ok, board_failed = _company_boards(config)
    out.ok += board_ok
    out.failed += len(board_failed)
    out.failed_names += board_failed
    out.by_source["company boards"] = len(board_jobs)

    feeds, feeds_failed = _run_feeds(s)
    out.ok += len(feeds)
    out.failed += len(feeds_failed)
    out.failed_names += feeds_failed

    postings: list[Posting] = [p for f in feeds.values() for p in f.postings]
    if "discovery" in s.sources:
        postings += discover.guess_postings()

    configured = {(c.ats, c.slug.lower()) for c in config.companies}
    enabled = set(s.sources)
    ats_kinds = {"greenhouse", "ashby", "lever"} & enabled

    stages: list[tuple[str, Callable[[], list[Job]]]] = []
    if ats_kinds:
        stages.append(("ats", lambda: ats.scrape(postings, ats_kinds, workers, deadline, skip=configured)))
    for name, module in (
        ("workday", workday), ("oracle", oracle), ("smartrecruiters", smartrecruiters), ("workable", workable),
        ("recruitee", recruitee), ("bamboohr", bamboohr), ("icims", icims), ("eightfold", eightfold),
        ("personio", personio),
    ):
        if name in enabled:
            stages.append((name, lambda m=module: m.scrape(postings, workers, deadline)))
    if "phenom" in enabled:
        stages.append(("phenom", lambda: phenom.scrape(workers, deadline)))

    direct: list[Job] = []
    results = parallel_map(stages, lambda st: st[1](), workers=3)
    for (name, _), res in zip(stages, results):
        if res is None:
            out.failed += 1
            out.failed_names.append(name)
            log.warning("source %s failed", name)
            continue
        out.ok += 1
        out.by_source[name] = len(res)
        direct += res

    feed_jobs = [j for n in ("github", "jobbank", "themuse") if n in feeds for j in feeds[n].jobs]
    adzuna_jobs = feeds["adzuna"].jobs if "adzuna" in feeds else []
    for name in ("github", "jobbank", "themuse", "adzuna"):
        if name in feeds:
            out.by_source[name] = len(feeds[name].jobs)
    out.jobs = board_jobs + direct + feed_jobs + adzuna_jobs
    return out
