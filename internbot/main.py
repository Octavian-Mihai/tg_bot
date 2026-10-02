"""Orchestrates fetch -> filter -> dedupe -> notify."""
from __future__ import annotations

import argparse
import logging
import sys

from internbot.config import Config, ConfigError, load_config
from internbot.filters import filter_internships
from internbot.formatting import format_messages
from internbot.models import Job
from internbot.notifier import NotifierError, TelegramNotifier
from internbot.sources import adzuna, greenhouse, lever
from internbot.sources.base import SourceError
from internbot.storage import Storage

log = logging.getLogger("internbot")

ATS_FETCHERS = {"greenhouse": greenhouse.fetch_jobs, "lever": lever.fetch_jobs}


def collect_jobs(config: Config) -> tuple[list[Job], int, int]:
    """Fetch from every source. One failing source never stops the others.

    Returns (jobs, sources_ok, sources_failed). Company boards come first so they win
    over Adzuna when the same posting appears in both.
    """
    jobs: list[Job] = []
    ok = failed = 0

    for company in config.companies:
        label = f"{company.ats}/{company.slug}"
        try:
            jobs += ATS_FETCHERS[company.ats](company.slug, company.name, config.locations)
            ok += 1
        except SourceError as exc:
            log.warning("source %s failed: %s", label, exc)
            failed += 1

    try:
        jobs += adzuna.fetch_from_env()
        ok += 1
    except SourceError as exc:
        log.warning("source adzuna failed: %s", exc)
        failed += 1

    return jobs, ok, failed


def run(dry_run: bool = False, config: Config | None = None) -> int:
    config = config or load_config()
    jobs, ok, failed = collect_jobs(config)
    log.info("sources: %d ok, %d failed; %d jobs fetched", ok, failed, len(jobs))
    if ok == 0:
        log.error("every source failed")
        return 1

    jobs = filter_internships(jobs)
    log.info("%d jobs after internship/tech filter", len(jobs))

    with Storage() as storage:
        jobs = storage.filter_new(jobs)
        log.info("%d new jobs (not seen before)", len(jobs))

        messages = format_messages(jobs)
        if not messages:
            log.info("nothing to send")
            return 0
        if dry_run:
            print("\n\n----- next message -----\n\n".join(messages))
            return 0
        notifier = TelegramNotifier.from_env()
        for msg in messages:
            notifier.send(msg)
        # Only mark seen after every message went out, so a failed send is retried next run.
        storage.mark_seen(jobs)
    log.info("sent %d message(s)", len(messages))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Notify me about new internships")
    parser.add_argument("--dry-run", action="store_true", help="print instead of sending")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    try:
        return run(dry_run=args.dry_run)
    except (ConfigError, NotifierError) as exc:
        log.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
