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
    source: str  # channel name, e.g. "adzuna", "workday"; the part of `id` before the first ":"
    description: str = ""  # plain text; empty when the source gives none
    term: str = "unstated"  # "summer-2027 winter-2027", "summer", "unstated" or "other-cycle"
    compensation: str = ""  # structured pay text when the source has it (Ashby)
    posted: str = ""  # ISO date (YYYY-MM-DD) the posting went up, when the source says

    @property
    def key(self) -> str:
        """Cross-source identity: the same posting on Adzuna and on a company board shares it."""
        return f"{normalize_text(self.company).strip()}|{normalize_text(self.title).strip()}"
