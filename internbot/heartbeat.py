"""Weekly check-in message so silence means something is wrong."""
from __future__ import annotations

import logging
import sys

from internbot.config import ConfigError, load_config
from internbot.notifier import NotifierError, TelegramNotifier
from internbot.storage import Storage

log = logging.getLogger("internbot")


def build_message(recent: int, total: int, n_companies: int) -> str:
    return (
        "internbot weekly check-in: still running ✅\n"
        f"New postings sent in the last 7 days: {recent}\n"
        f"Total postings tracked: {total}\n"
        f"Sources: Adzuna + {n_companies} company boards"
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        config = load_config()
        with Storage() as storage:
            recent, total = storage.stats(days=7)
        TelegramNotifier.from_env().send(build_message(recent, total, len(config.companies)))
    except (ConfigError, NotifierError) as exc:
        log.error("%s", exc)
        return 1
    log.info("heartbeat sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
