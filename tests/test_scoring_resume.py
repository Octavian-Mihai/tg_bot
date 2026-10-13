from dataclasses import replace

from internbot.models import Job
from internbot.profile import Profile
from internbot.resume import choose_resume
from internbot.scoring import company_tier, detect_skills, normalize_company, parse_pay, role_family, score_job


def job(title="Software Engineer Intern", description="", company="Acme", **kw):
    return Job(id="x:1", title=title, company=company, location="Montreal", url="https://e/1",
               source=kw.pop("source", "workday"), description=description, **kw)


def test_pay_parsing():
    assert parse_pay("$40 - $50 per hour").hourly == 45
    assert round(parse_pay("$8,000/month").hourly, 1) == 46.2
    assert parse_pay("CA$40 - CA$50 / hr").hourly == 45
    assert parse_pay("$120k/year").hourly == 120000 / 2080
    assert parse_pay("$3 per hour") is None and parse_pay("no pay mentioned") is None


def test_skill_detection_avoids_the_classic_false_positives():
    assert detect_skills("We use Python, SQL and Docker") == ["python", "sql", "docker"]
    assert "node" not in detect_skills("each compute node in the cluster")
    assert "node" in detect_skills("Node.js services") and "java" not in detect_skills("JavaScript only")
    assert detect_skills("go to market strategy") == []


def test_role_family_and_company_tier():
    assert role_family("Game AI Programmer Intern") == "game"
    assert role_family("Cybersecurity Analyst Intern") == "security"
    assert role_family("DevOps Intern") == "infra" and role_family("Software Intern") == "swe"
    assert normalize_company("Jane Street, Inc.") == "janestreet" and company_tier("Google LLC") == "top"
    assert company_tier("Shopify") == "strong" and company_tier("Local Shop") == "unknown"


def test_more_matching_skills_means_a_better_chance(profile):
    match = job(description="Python, SQL, Docker, TypeScript, React and git. Code reviews, mentorship.")
    miss = job(description="Rust, C++, Verilog, Kubernetes, Terraform, Kafka and Spark.")
    assert score_job(match, profile).chance > score_job(miss, profile).chance


def test_famous_companies_are_harder_to_get_but_better(profile):
    base = dict(description="Python and SQL. Mentorship. Return offer.")
    big = score_job(job(company="Google", **base), profile)
    small = score_job(job(company="Tiny Co", **base), profile)
    assert big.quality > small.quality and big.difficulty > small.difficulty


def test_unpaid_roles_are_capped_and_pay_is_rewarded(profile):
    assert score_job(job(description="This is an unpaid internship."), profile).quality <= 25
    paid = score_job(job(description="$45/hr"), profile)
    assert paid.pay == "$45/hr" and paid.quality > score_job(job(), profile).quality


def test_level_and_term_mismatches_lower_the_chance(profile):
    ok = score_job(job(description="Python SQL Docker"), profile).chance
    assert score_job(job(title="Senior Software Engineer", description="Python SQL Docker"), profile).chance < ok
    assert score_job(job(term="other-cycle", description="Python SQL Docker"), profile).chance < ok
    assert score_job(job(title="Software Intern / New Grad", description="Python SQL Docker"), profile).level_reason is None


def test_no_description_means_low_confidence(profile):
    assert score_job(job(), profile).confidence == "low"


def test_resume_follows_the_title_then_the_body(profile):
    assert choose_resume(job(title="Backend Developer Intern"), profile).variant == "backend"
    assert choose_resume(job(title="DevOps Intern"), profile).variant == "backend"
    assert choose_resume(job(title="iOS Developer Intern"), profile).variant == "ios"
    assert choose_resume(job(title="Machine Learning Intern"), profile).variant == "ai"
    assert choose_resume(job(title="Cybersecurity Intern"), profile).variant == "security"
    assert choose_resume(job(title="Software Developer Intern"), profile).variant == "fullstack"
    body = "CodeQL, SAST, OWASP vulnerabilities and DevSecOps in CI/CD pipelines."
    assert choose_resume(job(title="Software Developer Intern", description=body), profile).variant == "security"


def test_infra_roles_use_backend_unless_security_leads(profile):
    for title in ("DevOps Intern", "Site Reliability Engineer Intern", "Cloud Platform Intern"):
        assert choose_resume(job(title=title), profile).variant == "backend"
    infra_body = "Kubernetes, Terraform and Prometheus monitoring on AWS."
    assert choose_resume(job(title="DevOps Intern", description=infra_body), profile).variant == "backend"
    assert role_family("DevSecOps Intern") == "security"
    assert choose_resume(job(title="DevSecOps Intern"), profile).variant == "security"
    sec_body = "CodeQL, SAST, OWASP vulnerabilities and CVE triage in CI/CD."
    assert choose_resume(job(title="DevOps Intern", description=sec_body), profile).variant == "security"


def test_one_stray_signal_does_not_override_the_title(profile):
    c = choose_resume(job(title="Backend Developer Intern", description="HTML/CSS is a plus. React is nice."), profile)
    assert c.variant == "backend"


def test_a_resume_you_do_not_have_falls_back(profile):
    only_default = replace(profile, resumes=("fullstack",))
    c = choose_resume(job(title="Cybersecurity Intern"), only_default)
    assert c.variant == "fullstack" and "no security résumé on file" in c.reason
    no_security = replace(profile, resumes=("fullstack", "backend"))
    assert choose_resume(job(title="Cybersecurity Intern"), no_security).variant == "backend"


def test_default_profile_loads_and_flags_unknown_skills(tmp_path):
    from internbot.profile import load_profile

    f = tmp_path / "p.json"
    f.write_text('{"skills": ["python", "cobol"], "resumes": ["backend"]}')
    p = load_profile(f)
    assert p.skills == {"python"} and p.unknown_skills == ("cobol",) and p.resumes[0] == "fullstack"
    assert isinstance(load_profile(tmp_path / "missing.json"), Profile)
    assert load_profile().skills
