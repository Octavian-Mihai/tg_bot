from __future__ import annotations

from dataclasses import dataclass

from internbot.textutil import normalize_text


@dataclass(frozen=True)
class Job:
    id: str  # unique across sources, e.g. "adzuna:12345"
    title: str
    company: str
    location: str
    url: str
    source: str

    @property
    def key(self) -> str:
        """Cross-source identity: the same posting on Adzuna and on a company board shares it."""
        return f"{normalize_text(self.company).strip()}|{normalize_text(self.title).strip()}"
