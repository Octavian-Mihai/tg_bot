"""Scores a posting two ways, ported from Jobify's score.js.

    chance   0-100  fit minus how contested the role is. Difficulty only subtracts, so chance
                    never exceeds fit.
    quality  0-100  how good the internship is, whoever applies: pay, program signals, real-work
                    substance, company prestige.

Neither is calibrated or validated against outcomes. They exist to rank today's postings against
each other.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from internbot.lexicon import (
    DEFAULT_ROLE_FAMILY,
    HOURS_PER_MONTH,
    HOURS_PER_YEAR,
    PAY_CURVE,
    PAY_PATTERN,
    PAY_UNSTATED_SCORE,
    QUALITY_RED_FLAGS,
    QUALITY_SIGNALS,
    ROLE_FAMILIES,
    SKILL_LEXICON,
    STRONG_TIER_COMPANIES,
    TOP_TIER_COMPANIES,
)
from internbot.models import Job
from internbot.profile import Profile

SKILL_EVIDENCE_FLOOR = 3  # fewer detected skills than this and the skill score is blended toward neutral
NEUTRAL_SKILL_FIT = 55
COMPAT_WEIGHTS = {"skill": 0.6, "role": 0.4}
QUALITY_WEIGHTS = {"pay": 0.35, "program": 0.3, "substance": 0.2, "company": 0.15}
TIER_QUALITY = {"top": 95, "strong": 78, "unknown": 55}
RED_FLAG_CEILING = 25
DIFFICULTY_TIER = {"top": 85, "strong": 60, "unknown": 25}
DIFFICULTY_QUALITY_DRAW = 15  # a better internship draws more applicants
DIFFICULTY_NEUTRAL = 40
CHANCE_CONTEST_WEIGHT = 0.6
# Applying through a company's own board means you got there before the copies did.
DIRECT_CHANNELS = {
    "greenhouse", "lever", "ashby", "workday", "oracle", "smartrecruiters", "workable",
    "recruitee", "bamboohr", "icims", "eightfold", "personio", "phenom",
}

_LEGAL_SUFFIX = re.compile(r"\s*\b(inc|llc|ltd|corp|corporation|plc|gmbh|nv|sa|co)\.?\s*$", re.I)


def _clamp(n: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, n))


def _round(n: float) -> int:
    return int(round(_clamp(n, 0, 100)))


def _interpolate(curve: list[tuple[float, float]], x: float) -> float:
    if x <= curve[0][0]:
        return curve[0][1]
    for (x0, y0), (x1, y1) in zip(curve, curve[1:]):
        if x <= x1:
            return y0 + (x - x0) / (x1 - x0) * (y1 - y0)
    return curve[-1][1]


def normalize_company(name: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", name or "") if not unicodedata.combining(c)).strip()
    prev = None
    while s != prev:
        prev = s
        s = _LEGAL_SUFFIX.sub("", re.sub(r",\s*$", "", s))
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def company_tier(company: str) -> str:
    key = normalize_company(company)
    if key in TOP_TIER_COMPANIES:
        return "top"
    if key in STRONG_TIER_COMPANIES:
        return "strong"
    return "unknown"


def detect_skills(text: str) -> list[str]:
    if not text or not text.strip():
        return []
    return [skill for skill, pattern in SKILL_LEXICON.items() if pattern.search(text)]


def role_family(title: str) -> str:
    for family, pattern in ROLE_FAMILIES:
        if pattern.search(title or ""):
            return family
    return DEFAULT_ROLE_FAMILY


@dataclass(frozen=True)
class Pay:
    hourly: float
    raw: str


def parse_pay(text: str) -> Pay | None:
    m = PAY_PATTERN.search(text or "")
    if not m:
        return None
    lo, lo_k, hi, hi_k, unit = m.groups()

    def num(raw: str, k: str | None) -> float:
        return float(raw.replace(",", "")) * (1000 if k else 1)

    try:
        low = num(lo, lo_k)
        high = num(hi, hi_k) if hi else float("nan")
    except ValueError:
        return None
    amount = (low + high) / 2 if high == high and high >= low else low
    period = unit.lower()
    if period in ("hour", "hr"):
        hourly = amount
    elif period in ("month", "mo"):
        hourly = amount / HOURS_PER_MONTH
    else:
        hourly = amount / HOURS_PER_YEAR
    # A "$5000 per year" typo or a stray "$1M a year" figure is noise, not a wage.
    if not 5 <= hourly <= 500:
        return None
    return Pay(hourly, m.group(0).strip())


LEVEL_PATTERNS = {
    "phd": re.compile(r"\bph\.?d\b|\bdoctoral\b|\bdoctorate\b", re.I),
    "masters": re.compile(r"\bmaster'?s?\b(?!\s*of\s*none)|\bm\.?s\.?c?\.?\s+(?:required|student|candidate)", re.I),
    "new_grad": re.compile(r"\bnew\s*grad(?:uate)?s?\b|\bentry[\s-]*level\b|\bcampus\s*hire\b|\bgraduate\s+(?:programme?|scheme)\b", re.I),
    "senior": re.compile(r"\bsenior\b|\bstaff\b|\bprincipal\b|\blead\s+engineer\b|\b\d+\+?\s*years?\s+of\s+experience\b", re.I),
}
_PHD_REQUIRED = re.compile(
    r"\b(?:requires?|required|must\s+(?:be|have|hold)|open\s+only\s+to)\b[^.]{0,60}\bph\.?d\b|"
    r"\bph\.?d\b[^.]{0,40}\b(?:is\s+)?(?:required|mandatory|only)\b", re.I)
_UNDERGRAD_WELCOME = re.compile(r"\bbachelor'?s?\b|\bb\.?s\.?c?\.?\b|\bundergrad(?:uate)?\b", re.I)


def _level_mismatch(title: str, description: str) -> tuple[float, str | None]:
    if LEVEL_PATTERNS["phd"].search(title):
        return 0.15, "requires a PhD"
    if LEVEL_PATTERNS["new_grad"].search(title) and not re.search(r"\bintern|\bco-?op\b", title, re.I):
        return 0.2, "new-grad role, not an internship"
    if LEVEL_PATTERNS["senior"].search(title):
        return 0.15, "senior role"
    if LEVEL_PATTERNS["masters"].search(title):
        return 0.35, "requires a Master's"
    if _PHD_REQUIRED.search(description) and not _UNDERGRAD_WELCOME.search(description):
        return 0.7, "posting states a PhD is required"
    return 1.0, None


def _skill_fit(text: str, profile: Profile) -> tuple[float, list[str], list[str], bool]:
    required = detect_skills(text)
    matched = [s for s in required if s in profile.skills]
    thin = len(required) < SKILL_EVIDENCE_FLOOR
    if not required:
        return NEUTRAL_SKILL_FIT, matched, required, thin
    observed = 100 * (len(matched) / len(required)) ** 0.8
    observed += min(10, sum(1 for s in matched if s in profile.strong_skills) * 3.5)
    weight = min(1.0, len(required) / SKILL_EVIDENCE_FLOOR)
    return _clamp(observed * weight + NEUTRAL_SKILL_FIT * (1 - weight), 0, 100), matched, required, thin


def _role_fit(title: str, profile: Profile) -> tuple[float, str]:
    family = role_family(title)
    try:
        i = profile.preferred_families.index(family)
    except ValueError:
        return 40, family
    return _clamp(100 - i * 8, 30, 100), family


def _channel_difficulty(source: str) -> int:
    return -15 if (source or "").split(":")[0] in DIRECT_CHANNELS else 0


@dataclass(frozen=True)
class Score:
    chance: int
    quality: int
    confidence: str  # high | medium | low (low: no description to read)
    fit: int
    difficulty: int
    matched_skills: tuple[str, ...]
    required_skills: tuple[str, ...]
    family: str
    tier: str
    pay: str | None
    flags: tuple[str, ...]
    level_reason: str | None


def score_job(job: Job, profile: Profile) -> Score:
    desc = job.description or ""
    text = f"{job.title}\n{desc}"

    skill, matched, required, thin = _skill_fit(text, profile)
    role, family = _role_fit(job.title, profile)
    term_factor = 0.9 if job.term == "unstated" else 0.3 if job.term == "other-cycle" else 1.0
    level_factor, level_reason = _level_mismatch(job.title, desc)
    fit = _round((skill * COMPAT_WEIGHTS["skill"] + role * COMPAT_WEIGHTS["role"]) * term_factor * level_factor)

    tier = company_tier(job.company)
    pay = parse_pay(job.compensation) or parse_pay(desc)
    pay_score = _interpolate(PAY_CURVE, pay.hourly) if pay else PAY_UNSTATED_SCORE

    def has(name: str) -> bool:
        return bool(QUALITY_SIGNALS[name].search(desc))

    program = 40 + (25 if has("return_offer") else 0) + (20 if has("mentorship") else 0) \
        + (10 if has("cohort") else 0) + (5 if has("relocation") else 0)
    substance = 45 + (35 if has("ship") else 0) + (20 if has("review") else 0)
    flags = tuple(name for name, pat in QUALITY_RED_FLAGS.items() if pat.search(desc))

    quality = _round(
        pay_score * QUALITY_WEIGHTS["pay"] + program * QUALITY_WEIGHTS["program"]
        + substance * QUALITY_WEIGHTS["substance"] + TIER_QUALITY[tier] * QUALITY_WEIGHTS["company"]
    )
    if flags:
        quality = min(quality, RED_FLAG_CEILING)

    confidence = "low" if not desc.strip() else "high" if len(desc) > 800 and not thin else "medium"

    contest = DIFFICULTY_TIER[tier] + DIFFICULTY_QUALITY_DRAW * quality / 100 + _channel_difficulty(job.source)
    evidence = {"high": 1.0, "medium": 0.7, "low": 0.4}[confidence]
    difficulty = _round(DIFFICULTY_NEUTRAL + (contest - DIFFICULTY_NEUTRAL) * evidence)
    chance = _round(fit * (1 - CHANCE_CONTEST_WEIGHT * difficulty / 100))

    return Score(
        chance=chance, quality=quality, confidence=confidence, fit=fit, difficulty=difficulty,
        matched_skills=tuple(matched), required_skills=tuple(required), family=family, tier=tier,
        pay=pay.raw if pay else None, flags=flags, level_reason=level_reason,
    )
