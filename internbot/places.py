"""Decides whether a posting's location text is workable from Montreal.

Ported from Jobify's matchCity, narrowed to Montreal: the whole commutable metro counts
(a posting saying "Dorval" or "Brossard" is the same office market), and so does
remote-within-Canada, but only when the posting names no more specific place.
"""
from __future__ import annotations

import re

from internbot.textutil import normalize_text

DEFAULT_LOCATIONS = ["montreal", "quebec", "qc"]

# Suburb names unique to Quebec match bare; names that also exist elsewhere ("Laval",
# "Kirkland") are qualified with the province so a Kirkland, WA role can't slip in.
MONTREAL = re.compile(
    r"montr[eé]al|\b(?:longueuil|dorval|brossard|pointe[\s-]claire|lachine|outremont|pierrefonds|"
    r"dollard[\s-]des[\s-]ormeaux|c[oô]te[\s-]saint[\s-]luc|saint[\s-]l[eé]onard|boucherville|"
    r"terrebonne|repentigny|vaudreuil|saint[\s-]lambert|saint[\s-]bruno|candiac|"
    r"kirkland, ?(?:qc|qu[eé]bec)|laval, ?(?:qc|qu[eé]bec)|verdun, ?(?:qc|qu[eé]bec)|"
    r"anjou, ?(?:qc|qu[eé]bec)|lasalle, ?(?:qc|qu[eé]bec)|westmount, ?(?:qc|qu[eé]bec)|"
    r"saint[\s-]laurent, ?(?:qc|qu[eé]bec)|mont[\s-]royal, ?(?:qc|qu[eé]bec))\b",
    re.I,
)

# Remote-in-Canada needs an explicit Canada/Quebec token: that is what keeps foreign
# postings ("Utrecht, nl") out.
CANADA_TOKEN = re.compile(r"\bcanad(?:a|ian)\b|\bCAN\b|\bqu[eé]bec\b", re.I)

# Somewhere specific that is not Montreal. "Remote - Canada - ON" is an Ontario role.
NOT_MONTREAL = re.compile(
    r"\b(?:toronto|vancouver|ottawa|calgary|edmonton|winnipeg|halifax|saskatoon|regina|victoria|"
    r"burnaby|surrey|richmond|mississauga|markham|brampton|oakville|milton|hamilton|kitchener|"
    r"waterloo|cambridge|guelph|london|windsor|kingston|brockville|hawkesbury|ancaster|delta|"
    r"ashcroft|fredericton|moncton|st\.? ?john'?s|charlottetown|gatineau|kanata|sherbrooke|"
    r"trois[\s-]rivi[eè]res|saguenay|st ?j[eé]r[oô]me|saint[\s-]j[eé]r[oô]me)\b|\bontario\b|"
    r"\bbritish columbia\b|\balberta\b|\bmanitoba\b|\bsaskatchewan\b|\bnova scotia\b|"
    r"\bnew brunswick\b|\bnewfoundland\b|\bprince edward\b|[-,]\s*(?:ON|BC|AB|MB|SK|NS|NB|NL|PE)\b|"
    r"\b(?:ON|BC|AB|MB|SK|NS|NB|PE)\s*[-,]",
    re.I,
)

# Quebec City is in Quebec but is not Montreal; "Quebec, Quebec" means the city.
QUEBEC_CITY = re.compile(r"\bqu[eé]bec[\s,]+(?:city|qu[eé]bec\b)", re.I)


def is_remote_canada(text: str) -> bool:
    return bool(CANADA_TOKEN.search(text)) and not NOT_MONTREAL.search(text) and not QUEBEC_CITY.search(text)


def make_matcher(keywords: list[str], remote_canada: bool = True):
    pattern = re.compile(r"\b(" + "|".join(re.escape(normalize_text(k)) for k in keywords) + r")\b") if keywords else None

    def matches(text: str | None) -> bool:
        if not text:
            return False
        if MONTREAL.search(text):
            return True
        if pattern and pattern.search(normalize_text(text)):
            return True
        return remote_canada and is_remote_canada(text)

    return matches


_matcher = make_matcher(DEFAULT_LOCATIONS)


def configure(keywords: list[str], remote_canada: bool = True) -> None:
    """Set the matcher every source uses. Called once at startup from settings."""
    global _matcher
    _matcher = make_matcher(keywords, remote_canada)


def in_area(text: str | None) -> bool:
    return _matcher(text)
