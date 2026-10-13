"""Picks which résumé variant to send for a posting (ported from Jobify's resume.js).

The title's role family votes first; evidence in the body can override it only by a clear margin
and with more than one independent signal, so one stray "HTML/CSS a plus" can't attach the
frontend résumé to a backend job. Pure: same posting + same variants -> same answer.
"""
from __future__ import annotations

from dataclasses import dataclass

from internbot.lexicon import (
    DEFAULT_RESUME_VARIANT,
    DEFAULT_ROLE_FAMILY,
    RESUME_COMPANY_HINTS,
    RESUME_FALLBACK,
    RESUME_FAMILY_VARIANT,
    RESUME_FAMILY_WEIGHT,
    RESUME_MAX_DESCRIPTION_CHARS,
    RESUME_MIN_MARGIN,
    RESUME_MIN_SUPPORT,
    RESUME_SIGNALS,
    RESUME_TITLE_MULTIPLIER,
)
from internbot.models import Job
from internbot.profile import Profile
from internbot.scoring import role_family


@dataclass(frozen=True)
class ResumeChoice:
    variant: str
    family: str
    confident: bool
    reason: str  # short, human-readable evidence, e.g. "backend (databases, distributed systems)"


def _available(variant: str, have: tuple[str, ...]) -> str:
    """Follow the fallback chain until a variant the user actually has."""
    seen = set()
    while variant not in have and variant not in seen:
        seen.add(variant)
        variant = RESUME_FALLBACK.get(variant, DEFAULT_RESUME_VARIANT)
    return variant if variant in have else DEFAULT_RESUME_VARIANT


def choose_resume(job: Job, profile: Profile) -> ResumeChoice:
    title = job.title or ""
    description = (job.description or "")[:RESUME_MAX_DESCRIPTION_CHARS]
    company = job.company or ""

    family = role_family(title)
    family_variant = RESUME_FAMILY_VARIANT.get(family, DEFAULT_RESUME_VARIANT)
    variants = list(RESUME_SIGNALS)

    scores = {v: 0 for v in variants}
    matched: dict[str, list[str]] = {v: [] for v in variants}
    title_hits = {v: 0 for v in variants}

    if family != DEFAULT_ROLE_FAMILY and family_variant in scores:
        scores[family_variant] += RESUME_FAMILY_WEIGHT
        matched[family_variant].append(f"title reads as {family}")

    for variant, signals in RESUME_SIGNALS.items():
        for label, pattern, weight in signals:
            if pattern.search(title):
                scores[variant] += weight * RESUME_TITLE_MULTIPLIER
                matched[variant].append(f"{label} (title)")
                title_hits[variant] += 1
            elif pattern.search(description):
                scores[variant] += weight
                matched[variant].append(label)

    for label, variant, weight, pattern in RESUME_COMPANY_HINTS:
        if company and pattern.search(company):
            scores[variant] += weight
            matched[variant].append(f"{label} (company)")

    def rank(v: str):
        # Deterministic tie-break: the title's own variant, then base, then alphabetical.
        return (-scores[v], 0 if v == family_variant else 1 if v == DEFAULT_RESUME_VARIANT else 2, v)

    ranked = sorted(variants, key=rank)
    top, second = ranked[0], ranked[1]
    margin = scores[top] - scores[second]
    title_evidence = title_hits[top] > 0 or top == family_variant
    supported = title_evidence or len(matched[top]) >= RESUME_MIN_SUPPORT
    confident = margin >= RESUME_MIN_MARGIN and supported

    wanted = top if confident else family_variant
    variant = _available(wanted, profile.resumes)
    evidence = matched.get(wanted, [])[:3]
    reason = f"{variant} ({', '.join(evidence)})" if evidence else f"{variant} (no role-specific signal)"
    if variant != wanted:
        reason += f"; no {wanted} résumé on file"
    return ResumeChoice(variant=variant, family=family, confident=confident, reason=reason)
