from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Job:
    id: str  # unique across sources, e.g. "adzuna:12345"
    title: str
    company: str
    location: str
    url: str
    source: str
