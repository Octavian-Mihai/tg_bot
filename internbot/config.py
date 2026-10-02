"""Loads companies.toml (company boards to watch + location keywords)."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "companies.toml"
SUPPORTED_ATS = {"greenhouse", "lever"}
DEFAULT_LOCATIONS = ["montreal", "quebec", "qc"]


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Company:
    name: str
    ats: str
    slug: str


@dataclass(frozen=True)
class Config:
    locations: list[str] = field(default_factory=lambda: list(DEFAULT_LOCATIONS))
    companies: list[Company] = field(default_factory=list)


def load_config(path: str | os.PathLike | None = None) -> Config:
    path = Path(path or os.environ.get("INTERNBOT_CONFIG") or DEFAULT_PATH)
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from None

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
    return Config(locations=list(locations), companies=companies)
