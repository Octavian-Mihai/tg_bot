import pytest

from internbot import places
from internbot.models import Job
from internbot.profile import Profile


@pytest.fixture(autouse=True)
def default_places():
    places.configure(places.DEFAULT_LOCATIONS, True)
    yield
    places.configure(places.DEFAULT_LOCATIONS, True)


@pytest.fixture
def profile():
    return Profile()


@pytest.fixture
def make_job():
    def _make(n=1, title="Software Developer Intern", **kw):
        return Job(
            id=kw.get("id", f"adzuna:{n}"),
            title=title,
            company=kw.get("company", "Acme"),
            location=kw.get("location", "Montréal, QC"),
            url=kw.get("url", f"https://example.com/{n}"),
            source=kw.get("id", "adzuna:x").split(":")[0],
            description=kw.get("description", ""),
            term=kw.get("term", "unstated"),
            compensation=kw.get("compensation", ""),
        )

    return _make
