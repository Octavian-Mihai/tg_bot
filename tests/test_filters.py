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


def test_business_tracks_are_dropped_unless_the_title_is_clearly_technical(make_job):
    from internbot.filters import filter_internships, is_wanted_title

    kept = ["Software Engineer Intern - Finance", "Security Analyst Intern", "Stagiaire développeur - Marketing Technology"]
    dropped = ["Financial Accounting Analyst Intern", "Stagiaire analyste en comptabilité", "Sales Engineer Intern",
               "Data Analyst Intern, Recruiting"]
    assert [j.title for j in filter_internships([make_job(i, title=t) for i, t in enumerate(kept)])] == kept
    assert filter_internships([make_job(i, title=t) for i, t in enumerate(dropped)]) == []
    assert is_wanted_title("Application Developer", "campus") and not is_wanted_title("Accounting Analyst", "campus")
