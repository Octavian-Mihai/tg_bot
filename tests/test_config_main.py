import pytest

from internbot import collect as collect_mod
from internbot import main as main_mod
from internbot.config import Company, Config, ConfigError, Settings, load_config, load_settings
from internbot.sources.base import SourceError


def test_load_config(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('locations=["montreal"]\n[[company]]\nname="A"\nats="lever"\nslug="a"\n')
    cfg = load_config(f)
    assert cfg.locations == ["montreal"] and cfg.companies == [Company("A", "lever", "a")]


@pytest.mark.parametrize(
    "body", ['[[company]]\nname="A"\nats="lever"\n', '[[company]]\nname="A"\nats="workday"\nslug="a"\n', "not = toml ["]
)
def test_bad_config_raises(tmp_path, body):
    f = tmp_path / "c.toml"
    f.write_text(body)
    with pytest.raises(ConfigError):
        load_config(f)


def test_shipped_config_is_valid():
    cfg = load_config()
    assert cfg.companies and cfg.settings.schedule.weekday_hours


def test_settings_parse_and_validate(tmp_path):
    f = tmp_path / "s.toml"
    f.write_text(
        '[schedule]\nweekday_hours=[9,17]\nweekend_hours=[12]\n'
        '[notify]\npostings_per_message=5\ntell_me_when_nothing_new=false\n'
        '[trigger]\nkeywords=["Go", " "]\n[sources]\nworkday=false\n'
    )
    s = load_settings(f)
    assert s.schedule.weekday_hours == (9, 17) and s.schedule.weekend_hours == (12,)
    assert s.postings_per_message == 5 and s.tell_me_when_nothing_new is False
    assert s.trigger_keywords == ("go",) and "workday" not in s.sources and "lever" in s.sources


@pytest.mark.parametrize("body", ["[sources]\nbogus=true\n", "[schedule]\nweekday_hours=[25]\n"])
def test_bad_settings_raise(tmp_path, body):
    f = tmp_path / "s.toml"
    f.write_text(body)
    with pytest.raises(ConfigError):
        load_settings(f)


CFG = Config(
    companies=[Company("Acme", "greenhouse", "acme")],
    settings=Settings(sources=frozenset({"adzuna"})),
)


def _patch(monkeypatch, make_job, board_fails=False, adzuna_fails=False):
    def board(slug, name):
        if board_fails:
            raise SourceError("boom")
        return [make_job(1, id=f"greenhouse:{slug}:1")]

    def adz():
        if adzuna_fails:
            raise SourceError("boom")
        return [make_job(2, id="adzuna:2", title="Cybersecurity Intern")]

    monkeypatch.setitem(collect_mod.ATS_FETCHERS, "greenhouse", board)
    monkeypatch.setattr(collect_mod.adzuna, "fetch_from_env", adz)


def test_one_failing_source_does_not_stop_the_run(monkeypatch, make_job):
    _patch(monkeypatch, make_job, board_fails=True)
    got = collect_mod.collect(CFG)
    assert (got.ok, got.failed) == (1, 1) and [j.id for j in got.jobs] == ["adzuna:2"]
    assert got.failed_names == ["greenhouse/acme"]


def test_run_fails_only_when_every_source_fails(monkeypatch, make_job, tmp_path):
    monkeypatch.setenv("INTERNBOT_DB", str(tmp_path / "t.db"))
    _patch(monkeypatch, make_job, board_fails=True, adzuna_fails=True)
    assert main_mod.run(dry_run=True, config=CFG) == 1


class FakeNotifier:
    def __init__(self):
        self.sent = []

    def send(self, text, reply_markup=None):
        self.sent.append(text)


@pytest.fixture
def notifier(monkeypatch):
    fake = FakeNotifier()
    monkeypatch.setattr(main_mod.TelegramNotifier, "from_env", classmethod(lambda cls: fake))
    return fake


def test_run_sends_ranked_batch_then_says_nothing_new(monkeypatch, make_job, tmp_path, notifier, profile):
    monkeypatch.setenv("INTERNBOT_DB", str(tmp_path / "t.db"))
    _patch(monkeypatch, make_job)
    assert main_mod.run(config=CFG, profile=profile) == 0
    assert len(notifier.sent) == 1 and "2 new internship postings" in notifier.sent[0]
    assert "Résumé:" in notifier.sent[0] and "chance" in notifier.sent[0]
    assert main_mod.run(config=CFG, profile=profile) == 0
    assert len(notifier.sent) == 2 and "no new internship postings" in notifier.sent[1]


def test_silent_when_told_not_to_report_empty_runs(monkeypatch, make_job, tmp_path, notifier, profile):
    monkeypatch.setenv("INTERNBOT_DB", str(tmp_path / "t.db"))
    _patch(monkeypatch, make_job)
    quiet = Config(companies=CFG.companies, settings=Settings(sources=CFG.settings.sources, tell_me_when_nothing_new=False))
    main_mod.run(config=quiet, profile=profile)
    main_mod.run(config=quiet, profile=profile)
    assert len(notifier.sent) == 1


def test_all_postings_sent_in_groups(monkeypatch, make_job, tmp_path, notifier, profile):
    monkeypatch.setenv("INTERNBOT_DB", str(tmp_path / "t.db"))
    _patch(monkeypatch, make_job)
    small = Config(companies=CFG.companies, settings=Settings(sources=CFG.settings.sources, postings_per_message=1))
    main_mod.run(config=small, profile=profile)
    assert len(notifier.sent) == 2 and "message 1/2" in notifier.sent[0] and "message 2/2" in notifier.sent[1]
    main_mod.run(config=small, profile=profile)
    assert "no new internship postings" in notifier.sent[2]


def test_other_cycle_postings_are_dropped(monkeypatch, make_job, tmp_path, notifier, profile):
    monkeypatch.setenv("INTERNBOT_DB", str(tmp_path / "t.db"))
    monkeypatch.setitem(collect_mod.ATS_FETCHERS, "greenhouse", lambda slug, name: [
        make_job(1, id="greenhouse:a:1", term="other-cycle"),
        make_job(2, id="greenhouse:a:2", title="Winter Developer Intern", term="winter-2027"),
    ])
    monkeypatch.setattr(collect_mod.adzuna, "fetch_from_env", lambda: [])
    main_mod.run(config=CFG, profile=profile)
    assert "1 new internship posting," in notifier.sent[0] and "Winter 2027" in notifier.sent[0]


def test_canonical_url_ignores_tracking_and_slashes():
    a = main_mod.canonical_url("https://Jobs.Example.com/p/1/?utm_source=x#top")
    assert a == main_mod.canonical_url("https://jobs.example.com/p/1")


def test_the_same_role_listed_on_two_sites_is_one_posting(make_job):
    a = make_job(1, id="workday:https://x/Ext/job/1", url="https://x/Ext/job/1", description="Build things")
    b = make_job(2, id="workday:https://x/uni/job/1", url="https://x/uni/job/1", description="Build things")
    other_place = make_job(3, id="workday:https://x/Ext/job/3", url="https://x/Ext/job/3", description="Build things", location="Laval, QC")
    other_text = make_job(4, id="workday:https://x/Ext/job/4", url="https://x/Ext/job/4", description="Different role entirely")
    assert main_mod.dedupe_jobs([a, b, other_place, other_text]) == [a, other_place, other_text]
