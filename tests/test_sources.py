import pytest

from internbot.sources import greenhouse, lever
from internbot.sources.base import SourceError, get_json, location_matcher

AREA = ["montreal", "quebec", "qc"]


def test_location_matcher_is_accent_and_case_insensitive():
    m = location_matcher(AREA)
    assert m("Montréal, QC") and m("MONTREAL") and m("Quebec City, Québec")
    assert not m("Toronto, Ontario") and not m("Lisbon, Portugal")
    assert not m("")


def test_greenhouse_keeps_only_in_area_jobs(monkeypatch):
    data = {
        "jobs": [
            {"id": 1, "title": "Software Intern", "absolute_url": "https://g/1", "location": {"name": "Montréal, QC"}},
            {"id": 2, "title": "Software Intern", "absolute_url": "https://g/2", "location": {"name": "Toronto"}},
            {"id": 3, "title": "No url"},
        ]
    }
    monkeypatch.setattr(greenhouse, "get_json", lambda url, **kw: data)
    jobs = greenhouse.fetch_jobs("acme", "Acme")
    assert [j.id for j in jobs] == ["greenhouse:acme:1"]
    assert jobs[0].company == "Acme" and jobs[0].source == "greenhouse"


def test_lever_matches_any_listed_location(monkeypatch):
    data = [
        {"id": "a", "text": "DevOps Intern", "hostedUrl": "https://l/a",
         "categories": {"location": "Toronto", "allLocations": ["Toronto", "Montreal"]}},
        {"id": "b", "text": "DevOps Intern", "hostedUrl": "https://l/b", "categories": {"location": "Paris"}},
    ]
    monkeypatch.setattr(lever, "get_json", lambda url, **kw: data)
    jobs = lever.fetch_jobs("acme", "Acme")
    assert [j.id for j in jobs] == ["lever:acme:a"]


def test_lever_rejects_unexpected_shape(monkeypatch):
    monkeypatch.setattr(lever, "get_json", lambda url, **kw: {"error": "x"})
    with pytest.raises(SourceError):
        lever.fetch_jobs("acme", "Acme")


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code, self.ok, self._p = status, status < 400, payload

    def json(self):
        return self._p


def test_get_json_retries_server_errors_then_succeeds(monkeypatch):
    calls = iter([_Resp(503), _Resp(200, {"ok": 1})])
    monkeypatch.setattr("internbot.sources.base.requests.get", lambda *a, **k: next(calls))
    monkeypatch.setattr("internbot.sources.base.time.sleep", lambda s: None)
    assert get_json("https://x") == {"ok": 1}


def test_get_json_does_not_retry_client_errors_and_hides_url(monkeypatch):
    n = []
    monkeypatch.setattr(
        "internbot.sources.base.requests.get", lambda *a, **k: n.append(1) or _Resp(404)
    )
    with pytest.raises(SourceError) as exc:
        get_json("https://secret.example/?app_key=SECRET")
    assert len(n) == 1
    assert "SECRET" not in str(exc.value) and "404" in str(exc.value)


def test_greenhouse_fetches_descriptions_only_for_survivors_and_reads_the_term(monkeypatch):
    calls = []

    def fake(url, **kw):
        calls.append(url)
        if url.endswith("/jobs"):
            return {"jobs": [
                {"id": 1, "title": "Software Intern", "absolute_url": "https://g/1", "location": {"name": "Montreal"}},
                {"id": 2, "title": "Account Executive", "absolute_url": "https://g/2", "location": {"name": "Montreal"}},
                {"id": 3, "title": "Software Intern (Fall 2026)", "absolute_url": "https://g/3", "location": {"name": "Montreal"}},
            ]}
        return {"content": "&lt;p&gt;Join us for the Winter 2027 term. Python and SQL.&lt;/p&gt;"}

    monkeypatch.setattr(greenhouse, "get_json", fake)
    jobs = greenhouse.fetch_jobs("acme", "Acme")
    assert [j.id for j in jobs] == ["greenhouse:acme:1"]
    assert jobs[0].term == "winter-2027" and "Python and SQL" in jobs[0].description
    assert len(calls) == 2  # the listing plus one description


def test_greenhouse_names_an_unnamed_board_from_its_metadata(monkeypatch):
    def fake(url, **kw):
        if url.endswith("/jobs"):
            return {"jobs": [{"id": 1, "title": "Software Intern", "absolute_url": "https://g/1", "location": {"name": "Montreal"}}]}
        if url.endswith("/jobs/1"):
            return {"content": ""}
        return {"name": "Figure AI"}

    monkeypatch.setattr(greenhouse, "get_json", fake)
    assert greenhouse.fetch_jobs("figureai")[0].company == "Figure AI"
