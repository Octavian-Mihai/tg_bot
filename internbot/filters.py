from __future__ import annotations

import re

from internbot.models import Job
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

def is_internship(job: Job) -> bool:
    return bool(INTERNSHIP_RE.search(normalize_text(job.title)))


def is_tech(job: Job) -> bool:
    title = normalize_text(job.title)
    return bool(TECH_RE.search(title))


def filter_internships(jobs: list[Job]) -> list[Job]:
    """Keep internship postings whose title is IT / cybersecurity / devops / software related."""
    return [j for j in jobs if is_internship(j) and is_tech(j)]
