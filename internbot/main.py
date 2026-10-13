"""Orchestrates collect -> filter -> dedupe -> rank -> notify."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlparse
from zoneinfo import ZoneInfo

from internbot import places
from internbot.collect import ATS_FETCHERS, collect  # noqa: F401 - ATS_FETCHERS re-exported for tests
from internbot.config import Config, ConfigError, load_config
from internbot.filters import filter_internships
from internbot.formatting import format_empty, format_messages, sources_footer
from internbot.models import Job
from internbot.notifier import NotifierError, TelegramNotifier
from internbot.profile import Profile, load_profile
from internbot.ranking import rank_jobs
from internbot.storage import Storage
from internbot.textutil import normalize_text

log = logging.getLogger("internbot")


def canonical_url(url: str) -> str:
    """Same posting, same key: lowercase host, no fragment, trailing slash or tracking params."""
    u = urlparse(url)
    query = urlencode([(k, v) for k, v in parse_qsl(u.query) if not k.lower().startswith("utm_") and k.lower() not in ("ref", "source", "src")])
    return f"{u.scheme}://{(u.hostname or '').lower()}{u.path.rstrip('/')}{'?' + query if query else ''}"


def dedupe_jobs(jobs: list[Job]) -> list[Job]:
    """Drop repeats within a run. Earlier jobs win, so sources are passed in preference order.

    Same URL is one posting. So is the same company + title + place + text: a Workday tenant
    often lists one role on two of its sites ("Ext" and "uni") under different URLs.
    """
    seen_urls: set[str] = set()
    seen_same: set[tuple[str, str, str]] = set()
    out = []
    for job in jobs:
        url = canonical_url(job.url)
        same = (job.key, normalize_text(job.location), job.description[:300])
        if url in seen_urls or same in seen_same:
            continue
        seen_urls.add(url)
        seen_same.add(same)
        out.append(job)
    return out


def run(dry_run: bool = False, config: Config | None = None, profile: Profile | None = None) -> int:
    config = config or load_config()
    profile = profile or load_profile()
    settings = config.settings
    places.configure(config.locations, settings.remote_canada)

    got = collect(config)
    log.info("sources: %d ok, %d failed; %d jobs fetched %s", got.ok, got.failed, len(got.jobs), got.by_source)
    if got.ok == 0:
        log.error("every source failed")
        return 1

    jobs = dedupe_jobs(filter_internships(got.jobs))
    log.info("%d jobs after internship/tech/term filter", len(jobs))

    with Storage() as storage:
        fresh = storage.filter_new(jobs)
        log.info("%d new jobs (not seen before)", len(fresh))
        ranked = rank_jobs(fresh, profile, settings.priority_companies)

        if ranked:
            footer = sources_footer(got.ok, got.failed, got.failed_names)
            messages = format_messages(ranked, per_message=settings.postings_per_message, footer=footer)
        elif settings.tell_me_when_nothing_new:
            now = datetime.now(ZoneInfo(settings.schedule.timezone))
            messages = [format_empty(now, len(jobs), got.ok, got.failed, got.failed_names)]
        else:
            log.info("nothing to send")
            return 0

        if dry_run:
            print("\n\n----- next message -----\n\n".join(messages))
            return 0
        notifier = TelegramNotifier.from_env()
        for msg in messages:
            notifier.send(msg)
        # Mark postings seen only after every message went out, so a failed send is retried next run.
        storage.mark_seen([r.job for r in ranked])
        storage.save_postings(ranked)
    log.info("sent %d message(s) covering %d posting(s)", len(messages), len(ranked))
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
