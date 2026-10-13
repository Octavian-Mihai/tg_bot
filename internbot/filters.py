from __future__ import annotations

import re

from internbot.models import Job
from internbot.terms import is_wanted
from internbot.textutil import normalize_text

INTERNSHIP_RE = re.compile(
    r"\b(intern|interns|internship|stagiaire|stagiaires|stage|co-?op|alternance)\b"
)

# Matched against the lowercased, accent-stripped title.
TECH_RE = re.compile(
    r"\b("
    r"software|logiciel|developer|developpeur|developpement|development|programmer|programmeur|"
    r"engineer|engineering|ingenieur|devops|devsecops|sre|reliability|platform|infrastructure|"
    r"cloud|aws|azure|gcp|kubernetes|docker|backend|back-end|frontend|front-end|full-?stack|"
    r"web|mobile|ios|android|api|python|java|javascript|typescript|react|node|golang|rust|c\+\+|\.net|"
    r"cyber|cybersecurity|cybersecurite|security|securite|infosec|appsec|soc|pentest|"
    r"network|networking|reseau|reseaux|systems?|systemes?|sysadmin|"
    r"it|ti|informatique|information technology|technologies? de l'information|"
    r"data|donnees|machine learning|ml|ai|ia|intelligence artificielle|qa|quality assurance|"
    r"test|testing|automation|automatisation|analyste|analyst|embedded|firmware"
    r")\b"
)


# Business tracks that slip past TECH_RE through a loose word like "analyst" or "systems"
# ("Financial Accounting Analyst Intern"). They are dropped unless the title also names a
# clearly technical role ("Software Engineer Intern - Finance" stays).
NON_TECH_RE = re.compile(
    r"\b(accounting|accountant|comptab\w*|financ\w*|marketing|sales|vente\w*|human resources|"
    r"ressources humaines|recruit\w*|talent|legal|juridique|supply chain|merchandis\w*|payroll|paie|audit)\b"
)
STRONG_TECH_RE = re.compile(
    r"\b(software|logiciel\w*|developer|developpeu\w*|programm\w*|devops|devsecops|cyber\w*|security|securite|"
    r"appsec|infosec|full-?stack|back-?end|front-?end|machine learning|cloud)\b"
)


def _tech_title(normalized: str) -> bool:
    if not TECH_RE.search(normalized):
        return False
    return not (NON_TECH_RE.search(normalized) and not STRONG_TECH_RE.search(normalized))


def is_internship(job: Job) -> bool:
    return bool(INTERNSHIP_RE.search(normalize_text(job.title)))


def is_tech(job: Job) -> bool:
    return _tech_title(normalize_text(job.title))


def is_wanted_title(title: str, kind: str = "internship") -> bool:
    """Cheap title gate the scrapers apply before paying for a description fetch.

    kind="internship": the title must say intern/co-op and look like IT/software work.
    kind="campus": a student-only careers site, where every posting is an internship whether or
    not it says so ("Application Developer" on a campus portal), so only the tech check applies.
    """
    t = normalize_text(title or "")
    if not t.strip() or not _tech_title(t):
        return False
    return kind == "campus" or bool(INTERNSHIP_RE.search(t))


def filter_internships(jobs: list[Job]) -> list[Job]:
    """Keep internship postings whose title is IT / cybersecurity / devops / software related
    and whose hiring term isn't a Fall/Spring/past one."""
    return [j for j in jobs if is_internship(j) and is_tech(j) and is_wanted(j.term)]
