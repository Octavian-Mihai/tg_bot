"""Which hiring term (Summer / Winter of which year) a posting is for.

Adapted from Jobify's classifier, which only knew Summer 2027. Here the wanted terms are the
upcoming Winter and Summer terms, computed from today's date so they roll forward on their own:

    summer-2027   wanted
    winter-2027   wanted
    summer        a bare season in the title, no year; assumed to be the upcoming one
    unstated      says nothing about a term; kept, a human decides
    other-cycle   a Fall/Spring term, or a past or far-future year; dropped

Only a season+year phrase (or a start date) is trusted to *reject* a posting. A bare "2027" is
too weak: "graduating by 2027" appears in last cycle's listings too.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

from internbot.textutil import normalize_text

OTHER_CYCLE = "other-cycle"
UNSTATED = "unstated"

# A term starts in January (winter) or May (summer). A term stays applicable for a couple of
# months after its start, and nothing further than ~15 months ahead is real yet.
_TERM_START_MONTH = {"winter": 1, "summer": 5}
_GRACE = timedelta(days=75)
_HORIZON = timedelta(days=460)

_SEASON_ALIASES = {
    "summer": "summer", "ete": "summer",
    "winter": "winter", "hiver": "winter",
    "fall": "fall", "autumn": "fall", "automne": "fall",
    "spring": "spring", "printemps": "spring",
}
_SEASONS = "summer|winter|fall|autumn|spring|ete|hiver|automne|printemps"

# Text is accent-stripped and lowercased first, so "été 2027" arrives as "ete 2027".
_SEASON_YEAR = re.compile(rf"(?<![a-z])({_SEASONS})\s*(?:of\s*|de\s*)?['’]?\s*(20\d{{2}})\b")
_YEAR_SEASON = re.compile(rf"\b(20\d{{2}})\s+({_SEASONS})(?![a-z])")
# A season alone in a title ("Software Intern - Summer"); "Spring Boot" is a framework.
_TITLE_SEASON = re.compile(rf"(?<![a-z])({_SEASONS})(?![a-z])(?!\s*(?:boot|framework))")

_MONTHS = (
    r"jan(?:uary|vier)?|fev(?:rier|ruary)?|feb(?:ruary)?|mar(?:ch|s)?|a(?:pr|vr)(?:il)?|may|mai|"
    r"jun(?:e)?|juin|jul(?:y)?|juil(?:let)?|aug(?:ust)?|aout|sep(?:t(?:ember|embre)?)?|"
    r"oct(?:ober|obre)?|nov(?:ember|embre)?|dec(?:ember|embre)?"
)
_MONTH_YEAR = re.compile(rf"\b({_MONTHS})\.?\s*,?\s*(20\d{{2}})\b")
_SEASON_RANGE = re.compile(rf"\b({_MONTHS})\.?\s*(?:-|to|through|until|a|au)\s*(?:{_MONTHS})\.?\s*,?\s*(20\d{{2}})\b")
_START_WORD = re.compile(
    r"\bstart(?:s|ing|ed|\s+date)?\b|\bbegin(?:s|ning)?\b|\bcommenc\w*|\b(?:able|available)\s+to\b|"
    r"\bdebut\w*|\ba\s+(?:partir|compter)\b|\bdes\b|\bdisponible\b"
)
_RANGE_TAIL = re.compile(rf"^\s*(?:-|to|through|until|a|au)\s*(?:{_MONTHS})")


def upcoming_terms(today: date | None = None) -> set[tuple[str, int]]:
    """The (season, year) pairs worth applying to on `today`."""
    today = today or date.today()
    wanted = set()
    for year in range(today.year - 1, today.year + 3):
        for season, month in _TERM_START_MONTH.items():
            start = date(year, month, 1)
            if today - _GRACE <= start <= today + _HORIZON:
                wanted.add((season, year))
    return wanted


def term_label(season: str, year: int) -> str:
    return f"{season}-{year}"


def _month_season(word: str) -> str | None:
    if word.startswith(("jan", "fe")):
        return "winter"
    if word.startswith(("mar", "apr", "avr")):
        return "spring"
    if word in ("may", "mai") or word.startswith(("jun", "juin", "jul", "juil")):
        return "summer"
    if word.startswith(("sep", "oct")):
        return "fall"
    return None  # aug, nov, dec: no inference


def _mentions(text: str) -> set[tuple[str, int]]:
    found = {(_SEASON_ALIASES[s], int(y)) for s, y in _SEASON_YEAR.findall(text)}
    found |= {(_SEASON_ALIASES[s], int(y)) for y, s in _YEAR_SEASON.findall(text)}
    return found


def _start_date_mentions(text: str) -> set[tuple[str, int]]:
    found: set[tuple[str, int]] = set()
    for m in _MONTH_YEAR.finditer(text):
        before = text[max(0, m.start() - 24):m.start()]
        after = text[m.end():m.end() + 24]
        if _START_WORD.search(before) or re.match(r"^\s*start\b", after) or _RANGE_TAIL.match(after):
            season = _month_season(m.group(1))
            if season:
                found.add((season, int(m.group(2))))
    for m in _SEASON_RANGE.finditer(text):
        season = _month_season(m.group(1))
        if season:
            found.add((season, int(m.group(2))))
    return found


def _verdict(mentions: set[tuple[str, int]], wanted: set[tuple[str, int]]) -> str | None:
    hits = sorted(m for m in mentions if m in wanted)
    if hits:
        return " ".join(term_label(s, y) for s, y in hits)
    return OTHER_CYCLE if mentions else None


def classify_term(text: str, wanted: set[tuple[str, int]] | None = None) -> str:
    """Term label for free text (title + description)."""
    t = normalize_text(text or "")
    if not t.strip():
        return UNSTATED
    wanted = wanted if wanted is not None else upcoming_terms()
    verdict = _verdict(_mentions(t), wanted)
    if verdict:
        return verdict
    start = _start_date_mentions(t)
    # Several start dates are ambiguous (a program with rolling intakes): leave it to a human.
    if len(start) == 1:
        return _verdict(start, wanted) or UNSTATED
    return UNSTATED


def classify_posting(title: str, description: str = "", wanted: set[tuple[str, int]] | None = None) -> str:
    """Like classify_term, plus the title's bare season ("... Intern - Fall") as a last resort."""
    term = classify_term(f"{title or ''} {description or ''}", wanted)
    if term != UNSTATED:
        return term
    seasons = {_SEASON_ALIASES[s] for s in _TITLE_SEASON.findall(normalize_text(title or ""))}
    if not seasons:
        return UNSTATED
    bare = sorted(s for s in seasons if s in ("summer", "winter"))
    return " ".join(bare) if bare else OTHER_CYCLE


def term_for_season_field(season: str, hint_year: int, wanted: set[tuple[str, int]] | None = None) -> str:
    """Term for a feed that carries a `season` field ("Summer", "Winter", "Fall") and whose
    repository is scoped to one year."""
    wanted = wanted if wanted is not None else upcoming_terms()
    s = _SEASON_ALIASES.get(normalize_text(season or "").strip())
    if s is None:
        return UNSTATED
    if s in ("summer", "winter"):
        # A winter term of a "2027" cycle starts in January 2027; summer in May 2027.
        return term_label(s, hint_year) if (s, hint_year) in wanted else OTHER_CYCLE
    return OTHER_CYCLE


def term_for_source(hint_year: int | None, title: str, wanted: set[tuple[str, int]] | None = None) -> str:
    """Term for a posting from a board scoped to one cycle. The board's *name* is not
    evidence on its own, so the title can still veto it ("Fall 2026" in a 2027 board)."""
    if hint_year is None:
        return classify_posting(title, "", wanted)
    wanted = wanted if wanted is not None else upcoming_terms()
    from_title = classify_posting(title, "", wanted)
    if from_title != UNSTATED:
        return from_title
    return term_label("summer", hint_year) if ("summer", hint_year) in wanted else OTHER_CYCLE


def is_wanted(term: str) -> bool:
    return term != OTHER_CYCLE


def pretty_term(term: str) -> str:
    """'summer-2027 winter-2027' -> 'Summer 2027 · Winter 2027'; '' for unstated."""
    if term in (UNSTATED, OTHER_CYCLE, ""):
        return ""
    return " · ".join(p.replace("-", " ").title() for p in term.split())
