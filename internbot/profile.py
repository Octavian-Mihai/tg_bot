"""The candidate model that postings are ranked against (profile.json)."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from internbot.lexicon import SKILL_LEXICON

log = logging.getLogger(__name__)

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "profile.json"

DEFAULT_FAMILIES = ["swe", "infra", "security", "backend", "fullstack", "data", "frontend", "ml", "mobile", "embedded"]
DEFAULT_RESUMES = ["base", "backend", "frontend", "ai", "game", "security", "devops"]


@dataclass(frozen=True)
class Profile:
    skills: frozenset[str] = frozenset({"python", "typescript", "javascript", "react", "node", "sql", "docker", "git", "linux", "ci", "rest"})
    strong_skills: frozenset[str] = frozenset({"python", "typescript"})
    preferred_families: tuple[str, ...] = tuple(DEFAULT_FAMILIES)
    resumes: tuple[str, ...] = tuple(DEFAULT_RESUMES)  # the variants you actually have
    unknown_skills: tuple[str, ...] = field(default=())


def load_profile(path: str | os.PathLike | None = None) -> Profile:
    path = Path(path or os.environ.get("INTERNBOT_PROFILE") or DEFAULT_PATH)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Profile()
    except (OSError, ValueError) as exc:
        log.warning("could not read %s (%s); using the default profile", path.name, type(exc).__name__)
        return Profile()

    base = Profile()
    skills = data.get("skills", sorted(base.skills))
    strong = data.get("strongSkills", sorted(base.strong_skills))
    unknown = tuple(s for s in [*skills, *strong] if s not in SKILL_LEXICON)
    if unknown:
        log.warning("profile.json lists skills the lexicon doesn't know, ignored: %s", ", ".join(unknown))
    resumes = tuple(data.get("resumes") or base.resumes)
    if "base" not in resumes:
        resumes = ("base", *resumes)
    return Profile(
        skills=frozenset(s for s in skills if s in SKILL_LEXICON),
        strong_skills=frozenset(s for s in strong if s in SKILL_LEXICON),
        preferred_families=tuple(data.get("preferredFamilies") or base.preferred_families),
        resumes=resumes,
        unknown_skills=unknown,
    )
