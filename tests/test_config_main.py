import pytest

from internbot import main as main_mod
from internbot.config import Config, ConfigError, Company, load_config
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
    assert load_config().companies


def _patch(monkeypatch, make_job, board_fails=False, adzuna_fails=False):
    def board(slug, name, locs):
        if board_fails:
            raise SourceError("boom")
        return [make_job(1, id=f"greenhouse:{slug}:1")]

    def adz():
        if adzuna_fails:
            raise SourceError("boom")
        return [make_job(2, id="adzuna:2", title="Cybersecurity Intern")]

    monkeypatch.setitem(main_mod.ATS_FETCHERS, "greenhouse", board)
    monkeypatch.setattr(main_mod.adzuna, "fetch_from_env", adz)


CFG = Config(companies=[Company("Acme", "greenhouse", "acme")])


def test_one_failing_source_does_not_stop_the_run(monkeypatch, make_job):
    _patch(monkeypatch, make_job, board_fails=True)
    jobs, ok, failed = main_mod.collect_jobs(CFG)
    assert (ok, failed) == (1, 1) and [j.id for j in jobs] == ["adzuna:2"]


def test_run_fails_only_when_every_source_fails(monkeypatch, make_job, tmp_path):
    monkeypatch.setenv("INTERNBOT_DB", str(tmp_path / "t.db"))
    _patch(monkeypatch, make_job, board_fails=True, adzuna_fails=True)
    assert main_mod.run(dry_run=True, config=CFG) == 1


def test_run_sends_and_marks_seen(monkeypatch, make_job, tmp_path):
    monkeypatch.setenv("INTERNBOT_DB", str(tmp_path / "t.db"))
    _patch(monkeypatch, make_job)
    sent = []

    class Fake:
        def send(self, text):
            sent.append(text)

    monkeypatch.setattr(main_mod.TelegramNotifier, "from_env", classmethod(lambda cls: Fake()))
    assert main_mod.run(config=CFG) == 0 and len(sent) == 1
    assert main_mod.run(config=CFG) == 0 and len(sent) == 1  # second run: nothing new
