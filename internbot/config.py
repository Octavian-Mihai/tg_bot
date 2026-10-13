"""Loads companies.toml (company boards to watch + location keywords) and settings.toml
(schedule, Telegram keywords, which sources are on)."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "companies.toml"
DEFAULT_SETTINGS_PATH = ROOT / "settings.toml"
SUPPORTED_ATS = {"greenhouse", "lever"}
DEFAULT_LOCATIONS = ["montreal", "quebec", "qc"]

# Every source family, all on by default. `settings.toml [sources]` switches any off.
ALL_SOURCES = (
    "github", "jobbank", "themuse", "adzuna", "levelsfyi", "hnhiring", "discovery",
    "greenhouse", "lever", "ashby", "workday", "oracle", "smartrecruiters", "workable",
    "recruitee", "bamboohr", "icims", "eightfold", "personio", "phenom",
)


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Company:
    name: str
    ats: str
    slug: str


@dataclass(frozen=True)
class Schedule:
    timezone: str = "America/Toronto"
    weekday_hours: tuple[int, ...] = (6, 8, 10, 12, 14, 16, 18, 20, 22)
    weekend_hours: tuple[int, ...] = (8, 12, 16, 20)
    catch_up_hours: int = 6  # a missed slot is still run if it is at most this old
    max_attempts: int = 3  # tries per slot before giving up on it


@dataclass(frozen=True)
class Settings:
    schedule: Schedule = field(default_factory=Schedule)
    postings_per_message: int = 20  # every new posting is sent, this many per message
    tell_me_when_nothing_new: bool = True
    trigger_keywords: tuple[str, ...] = ("check", "run", "jobs", "now", "scan", "refresh")
    remote_canada: bool = True
    sources: frozenset[str] = frozenset(ALL_SOURCES)
    concurrency: int = 16
    time_budget_minutes: int = 14  # stop starting new board fetches after this long
    priority_companies: tuple[str, ...] = ()  # lower-cased names that rank first


@dataclass(frozen=True)
class Config:
    locations: list[str] = field(default_factory=lambda: list(DEFAULT_LOCATIONS))
    companies: list[Company] = field(default_factory=list)
    settings: Settings = field(default_factory=Settings)


def _read_toml(path: Path, what: str) -> dict:
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh)
    except FileNotFoundError:
        raise ConfigError(f"{what} file not found: {path}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from None


def _hours(value, name: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not all(isinstance(h, int) and 0 <= h <= 23 for h in value):
        raise ConfigError(f"[schedule] {name} must be a list of hours 0-23")
    return tuple(sorted(set(value)))


def load_settings(path: str | os.PathLike | None = None) -> Settings:
    explicit = path or os.environ.get("INTERNBOT_SETTINGS")
    p = Path(explicit) if explicit else DEFAULT_SETTINGS_PATH
    if not explicit and not p.exists():
        return Settings()
    data = _read_toml(p, "settings")
    base = Settings()
    sched = data.get("schedule", {})
    schedule = Schedule(
        timezone=sched.get("timezone", base.schedule.timezone),
        weekday_hours=_hours(sched["weekday_hours"], "weekday_hours") if "weekday_hours" in sched else base.schedule.weekday_hours,
        weekend_hours=_hours(sched["weekend_hours"], "weekend_hours") if "weekend_hours" in sched else base.schedule.weekend_hours,
        catch_up_hours=int(sched.get("catch_up_hours", base.schedule.catch_up_hours)),
        max_attempts=int(sched.get("max_attempts", base.schedule.max_attempts)),
    )
    notify = data.get("notify", {})
    trigger = data.get("trigger", {})
    sources_cfg = data.get("sources", {})
    unknown = set(sources_cfg) - set(ALL_SOURCES)
    if unknown:
        raise ConfigError(f"[sources] unknown source(s): {', '.join(sorted(unknown))}")
    enabled = {s for s in ALL_SOURCES if sources_cfg.get(s, True)}
    limits = data.get("limits", {})
    keywords = tuple(str(k).strip().lower() for k in trigger.get("keywords", base.trigger_keywords) if str(k).strip())
    return Settings(
        schedule=schedule,
        postings_per_message=int(notify.get("postings_per_message", base.postings_per_message)),
        tell_me_when_nothing_new=bool(notify.get("tell_me_when_nothing_new", base.tell_me_when_nothing_new)),
        trigger_keywords=keywords,
        remote_canada=bool(data.get("search", {}).get("remote_canada", base.remote_canada)),
        sources=frozenset(enabled),
        concurrency=int(limits.get("concurrency", base.concurrency)),
        time_budget_minutes=int(limits.get("time_budget_minutes", base.time_budget_minutes)),
        priority_companies=tuple(str(n).strip().lower() for n in data.get("priority", {}).get("companies", []) if str(n).strip()),
    )


def load_config(path: str | os.PathLike | None = None, settings_path: str | os.PathLike | None = None) -> Config:
    path = Path(path or os.environ.get("INTERNBOT_CONFIG") or DEFAULT_PATH)
    data = _read_toml(path, "config")

    companies = []
    for i, entry in enumerate(data.get("company", []), start=1):
        missing = {"name", "ats", "slug"} - entry.keys()
        if missing:
            raise ConfigError(f"company #{i}: missing {', '.join(sorted(missing))}")
        if entry["ats"] not in SUPPORTED_ATS:
            raise ConfigError(
                f"company {entry['name']!r}: ats must be one of {sorted(SUPPORTED_ATS)}"
            )
        companies.append(Company(entry["name"], entry["ats"], entry["slug"]))
    locations = data.get("locations") or DEFAULT_LOCATIONS
    return Config(locations=list(locations), companies=companies, settings=load_settings(settings_path))
