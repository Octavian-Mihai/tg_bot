import pytest

from internbot.models import Job


@pytest.fixture
def make_job():
    def _make(n=1, title="Software Developer Intern", **kw):
        return Job(
            id=kw.get("id", f"adzuna:{n}"),
            title=title,
            company=kw.get("company", "Acme"),
            location=kw.get("location", "Montréal, QC"),
            url=kw.get("url", f"https://example.com/{n}"),
            source="adzuna",
        )

    return _make
