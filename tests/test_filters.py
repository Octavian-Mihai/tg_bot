import pytest

from internbot.filters import filter_internships


@pytest.mark.parametrize(
    "title",
    [
        "Backend Developer Intern, Winter 2027",
        "Stagiaire en cybersécurité",
        "Stagiaire - Développeur logiciel",
        "DevOps Co-op",
        "Stagiaire en réseautique TI",
        "Data Analyst Intern",
        "Stage - Soutien informatique",
    ],
)
def test_relevant_titles_kept(make_job, title):
    assert filter_internships([make_job(1, title=title)])


@pytest.mark.parametrize(
    "title",
    [
        "Stagiaire en marketing",
        "International Business Intern",
        "Intermediate Software Developer",
        "Summer Intern, Finance",
    ],
)
def test_irrelevant_titles_dropped(make_job, title):
    assert not filter_internships([make_job(1, title=title)])
