from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from internbot import listen
from internbot.config import Schedule
from internbot.schedule import decide, done, latest_due_slot, slot_id

TZ = ZoneInfo("America/Toronto")
S = Schedule()  # weekdays 6,8,...,22; weekends 8,12,16,20; catch up 6h; 3 attempts


def at(day, hour, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=TZ)  # Oct 13 2026 is a Tuesday


def test_slot_is_due_once_its_time_has_come():
    assert latest_due_slot(at(13, 9, 59), S) == at(13, 8)
    assert latest_due_slot(at(13, 10, 0), S) == at(13, 10)


def test_weekend_uses_its_own_hours():
    assert latest_due_slot(at(17, 11, 0), S) == at(17, 8)  # Saturday: no 10:00 slot
    assert latest_due_slot(at(17, 12, 5), S) == at(17, 12)


def test_slots_older_than_the_catch_up_window_are_ignored():
    assert latest_due_slot(at(13, 3, 0), S) == at(12, 22)  # 5h after the previous night's last slot
    assert latest_due_slot(at(13, 5, 0), S) is None  # 7h: too stale


def test_late_github_runs_still_get_their_slot():
    # GitHub fired the 10:00 slot 50 minutes late: still run it, exactly once
    d = decide(at(13, 10, 50), S, last_slot=slot_id(at(13, 8)), attempts=0)
    assert d.run and d.slot == slot_id(at(13, 10))
    assert not decide(at(13, 11, 5), S, last_slot=slot_id(at(13, 10)), attempts=0).run


def test_a_skipped_slot_is_caught_up_and_failures_are_retried_then_dropped():
    assert decide(at(13, 12, 20), S, last_slot=slot_id(at(13, 8)), attempts=0).run
    assert decide(at(13, 12, 20), S, last_slot=slot_id(at(13, 10)), attempts=2).run
    assert not decide(at(13, 12, 20), S, last_slot=slot_id(at(13, 10)), attempts=3).run


def test_manual_runs_always_go_and_use_no_slot():
    d = decide(at(13, 3, 0), S, last_slot="9999", attempts=9, manual=True)
    assert d.run and d.slot == ""


def test_dst_is_handled_by_the_timezone_not_by_hand():
    # 2026-11-01 is when Toronto falls back; 10:00 local is still 10:00 local
    after = datetime(2026, 11, 2, 10, 5, tzinfo=TZ)
    assert latest_due_slot(after, S) == datetime(2026, 11, 2, 10, tzinfo=TZ)


def test_done_only_moves_forward(tmp_path, monkeypatch):
    from internbot.storage import Storage

    monkeypatch.setenv("INTERNBOT_DB", str(tmp_path / "t.db"))
    done("2026-10-13T10")
    done("2026-10-13T08")
    with Storage() as s:
        assert s.get_meta("last_slot") == "2026-10-13T10"


@pytest.mark.parametrize("text,expected", [
    ("check", True), ("Check", True), ("/check", True), ("/check@my_bot", True), ("check now please", True),
    ("jobs!", True), ("hello there", False), ("", False), (None, False), ("recheck", False),
])
def test_keyword_detection(text, expected):
    assert listen.is_trigger(text, ["check", "jobs"]) is expected


class Calls:
    def __init__(self, updates):
        self.updates, self.sent, self.dispatched, self.confirmed = updates, [], [], []

    def install(self, monkeypatch):
        monkeypatch.setattr(listen, "pending_messages", lambda token, chat, now=None: (
            [m for m in self.updates], max(range(1, len(self.updates) + 1), default=None) if self.updates else None))
        monkeypatch.setattr(listen, "reply", lambda token, chat, text: self.sent.append(text))
        monkeypatch.setattr(listen, "dispatch", lambda repo, ref, tok: self.dispatched.append((repo, ref)))
        monkeypatch.setattr(listen, "pending_taps", lambda token, chat: [])
        monkeypatch.setattr(listen, "confirm", lambda token, last: self.confirmed.append(last))
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
        monkeypatch.setenv("GITHUB_REPOSITORY", "me/repo")
        monkeypatch.setenv("GITHUB_TOKEN", "g")
        monkeypatch.setenv("GITHUB_REF_NAME", "main")


def test_keyword_starts_the_workflow_then_confirms(monkeypatch):
    c = Calls([{"text": "hello"}, {"text": "/check"}])
    c.install(monkeypatch)
    assert listen.run() == 0
    assert c.dispatched == [("me/repo", "main")] and "On it" in c.sent[0] and c.confirmed == [2]


def test_chatter_is_ignored_and_confirmed(monkeypatch):
    c = Calls([{"text": "lol thanks"}])
    c.install(monkeypatch)
    assert listen.run() == 0 and not c.dispatched and not c.sent and c.confirmed == [1]


def test_help_lists_the_keywords(monkeypatch):
    c = Calls([{"text": "/start"}])
    c.install(monkeypatch)
    listen.run()
    assert "check" in c.sent[0] and not c.dispatched


def test_a_failed_dispatch_is_not_confirmed_so_it_retries(monkeypatch):
    c = Calls([{"text": "check"}])
    c.install(monkeypatch)

    def boom(repo, ref, tok):
        raise listen.ListenError("GitHub dispatch failed (HTTP 403)")

    monkeypatch.setattr(listen, "dispatch", boom)
    with pytest.raises(listen.ListenError):
        listen.run()
    assert not c.confirmed


def test_messages_from_strangers_and_stale_ones_never_count():
    import time

    updates = {"result": [
        {"update_id": 1, "message": {"chat": {"id": 7}, "date": time.time(), "text": "check"}},
        {"update_id": 2, "message": {"chat": {"id": 42}, "date": time.time() - 99999, "text": "check"}},
        {"update_id": 3, "message": {"chat": {"id": 42}, "date": time.time(), "text": "check"}},
    ]}
    orig = listen._call
    listen._call = lambda url, payload=None, headers=None: updates
    try:
        mine, last = listen.pending_messages("t", "42")
    finally:
        listen._call = orig
    assert len(mine) == 1 and last == 3


def _kb(*nums):
    return [[{"text": "x", "callback_data": f"a:{n}"}, {"text": "y", "callback_data": f"s:{n}"}] for n in nums]


def test_tap_collapses_only_that_posting_and_undo_restores_it():
    new, toast = listen.apply_tap("a:2", _kb(1, 2, 3))
    assert toast == "Marked applied" and len(new) == 3
    assert new[1] == [{"text": "✅ Applied 2 · undo", "callback_data": "u:2"}]
    assert new[0] == _kb(1)[0] and new[2] == _kb(3)[0]
    restored, _ = listen.apply_tap("u:2", new)
    assert restored[1][0]["callback_data"] == "a:2" and restored[1][1]["callback_data"] == "s:2"


def test_skip_tap_and_foreign_taps():
    new, _ = listen.apply_tap("s:1", _kb(1))
    assert new[0][0]["text"].startswith("🚫 Skipped")
    assert listen.apply_tap("zzz", _kb(1)) is None and listen.apply_tap("a:9", _kb(1)) is None


def test_taps_are_handled_before_confirming(monkeypatch):
    calls = []
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "t")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(listen, "pending_messages", lambda token, chat, now=None: ([], 7))
    tap = {"id": "q", "data": "a:1", "message": {"chat": {"id": 42}, "message_id": 5,
                                                   "reply_markup": {"inline_keyboard": _kb(1)}}}
    monkeypatch.setattr(listen, "pending_taps", lambda token, chat: [tap])
    monkeypatch.setattr(listen, "_call", lambda url, payload=None, headers=None: calls.append(url.rsplit("/", 1)[1]) or {})
    monkeypatch.setattr(listen, "confirm", lambda token, last: calls.append(f"confirm{last}"))
    assert listen.run() == 0
    assert calls == ["editMessageReplyMarkup", "answerCallbackQuery", "confirm7"]
