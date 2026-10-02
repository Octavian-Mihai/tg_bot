"""Orchestrates fetch -> filter -> format -> send."""
from __future__ import annotations

import argparse
import logging
import sys

from internbot.filters import filter_internships
from internbot.formatting import format_messages
from internbot.notifier import NotifierError, TelegramNotifier
from internbot.sources import adzuna
from internbot.storage import Storage

log = logging.getLogger("internbot")


def run(dry_run: bool = False) -> int:
    jobs = adzuna.fetch_from_env()
    log.info("fetched %d jobs", len(jobs))
    jobs = filter_internships(jobs)
    log.info("%d jobs after internship filter", len(jobs))

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
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        return run(dry_run=args.dry_run)
    except (adzuna.AdzunaError, NotifierError) as exc:
        log.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
