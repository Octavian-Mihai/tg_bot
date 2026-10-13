"""Decides whether a scheduled run is due, so every slot in settings.toml actually runs.

GitHub's cron is UTC-only, is routinely delayed by many minutes and sometimes drops runs
entirely. Hard-coding "run if the hour is 6, 8, 10..." therefore loses every slot GitHub is late
for. Instead the workflow wakes every 15 minutes and asks this module whether a configured slot
has come due that hasn't been completed. A skipped slot is caught up at the next wake-up; a
failed slot is retried until `max_attempts`.

    python -m internbot.schedule check   # prints run=true|false (+ slot) for $GITHUB_OUTPUT
    python -m internbot.schedule done --slot ID
    python -m internbot.schedule failed --slot ID
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from internbot.config import ConfigError, Schedule, load_settings
from internbot.storage import Storage

LAST_SLOT = "last_slot"


@dataclass(frozen=True)
class Decision:
    run: bool
    slot: str  # "" for a manual run
    reason: str


def slot_id(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H")  # sorts chronologically


def latest_due_slot(now: datetime, sched: Schedule) -> datetime | None:
    """The most recent configured slot at or before `now`, if it is within the catch-up window."""
    tz = ZoneInfo(sched.timezone)
    local = now.astimezone(tz)
    best: datetime | None = None
    for back in (0, 1):
        day = (local - timedelta(days=back)).date()
        hours = sched.weekend_hours if day.weekday() >= 5 else sched.weekday_hours
        for hour in hours:
            slot = datetime(day.year, day.month, day.day, hour, tzinfo=tz)
            if slot <= local and local - slot <= timedelta(hours=sched.catch_up_hours):
                if best is None or slot > best:
                    best = slot
    return best


def decide(now: datetime, sched: Schedule, last_slot: str | None, attempts: int, manual: bool = False) -> Decision:
    if manual:
        return Decision(True, "", "manual run")
    slot = latest_due_slot(now, sched)
    if slot is None:
        return Decision(False, "", "no slot is due")
    sid = slot_id(slot)
    if last_slot and sid <= last_slot:
        return Decision(False, sid, f"slot {sid} already done")
    if attempts >= sched.max_attempts:
        return Decision(False, sid, f"slot {sid} failed {attempts} times; giving up on it")
    late = int((now.astimezone(slot.tzinfo) - slot).total_seconds() // 60)
    return Decision(True, sid, f"slot {sid} is due ({late} min ago)")


def _attempts_key(slot: str) -> str:
    return f"attempts:{slot}"


def _write_output(decision: Decision) -> None:
    lines = [f"run={'true' if decision.run else 'false'}", f"slot={decision.slot}"]
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    print(f"{decision.reason} -> run={decision.run}")


def check(manual: bool) -> Decision:
    sched = load_settings().schedule
    now = datetime.now(ZoneInfo("UTC"))
    with Storage() as storage:
        slot = latest_due_slot(now, sched)
        attempts = int(storage.get_meta(_attempts_key(slot_id(slot))) or 0) if slot else 0
        decision = decide(now, sched, storage.get_meta(LAST_SLOT), attempts, manual)
    _write_output(decision)
    return decision


def done(slot: str) -> None:
    if not slot:
        return
    with Storage() as storage:
        if slot > (storage.get_meta(LAST_SLOT) or ""):
            storage.set_meta(LAST_SLOT, slot)


def failed(slot: str) -> None:
    """Count the failed attempt, and tell the user once it has been given up on."""
    sched = load_settings().schedule
    if not slot:
        attempt, left = 1, 0
    else:
        with Storage() as storage:
            attempt = int(storage.get_meta(_attempts_key(slot)) or 0) + 1
            storage.set_meta(_attempts_key(slot), str(attempt))
        left = max(0, sched.max_attempts - attempt)
    try:
        from internbot.notifier import NotifierError, TelegramNotifier

        retry = f"I'll retry at the next check ({left} attempt{'s' if left != 1 else ''} left)." if left else "Giving up on this slot; the next one runs as normal."
        TelegramNotifier.from_env().send(f"⚠️ internbot run failed (attempt {attempt}). {retry}\nSee the Actions tab for the log.")
    except Exception as exc:  # noqa: BLE001 - the alert is best-effort
        print(f"could not send failure alert: {type(exc).__name__}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scheduled-slot bookkeeping")
    parser.add_argument("command", choices=["check", "done", "failed"])
    parser.add_argument("--slot", default="")
    parser.add_argument("--manual", action="store_true", help="a manual/keyword-triggered run: always run")
    args = parser.parse_args()
    try:
        if args.command == "check":
            check(args.manual)
        elif args.command == "done":
            done(args.slot)
        else:
            failed(args.slot)
    except ConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
