"""Polls the Telegram bot for a keyword and, when the owner sends one, starts the daily workflow.

Run by .github/workflows/listen.yml every few minutes. Stdlib only, so the workflow needs no
`pip install`. Telegram keeps unconfirmed messages for 24 hours, so no state is stored here:
read the pending messages, act on them, then confirm them by asking for `offset = last id + 1`.
Messages are confirmed only after the action succeeded, so a failed dispatch is retried at the
next poll. Only messages from TELEGRAM_CHAT_ID are obeyed.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from internbot.config import ConfigError, load_settings

MAX_AGE_SECONDS = 2 * 3600  # a "check" sent yesterday shouldn't fire today
WORKFLOW = "daily.yml"
HELP = (
    "internbot commands (send any of these words, with or without a slash):\n"
    "{keywords}\n"
    "I look for new internships right away and message you the results."
)


class ListenError(RuntimeError):
    pass


def _call(url: str, payload: dict | None = None, headers: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        # Never include the URL: the Telegram one carries the bot token.
        raise ListenError(f"HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ListenError(type(exc).__name__) from None
    return json.loads(body) if body else {}


def parse_keyword(text: str | None) -> str:
    """'/Check@internbot_bot please' -> 'check'."""
    first = (text or "").strip().lower().split(maxsplit=1)
    if not first:
        return ""
    return re.sub(r"@\w+$", "", first[0].lstrip("/")).strip(".,!?")


def is_trigger(text: str | None, keywords: tuple[str, ...] | list[str]) -> bool:
    return parse_keyword(text) in {k.lower() for k in keywords}


def pending_messages(token: str, chat_id: str, now: float | None = None) -> tuple[list[dict], int | None]:
    """(messages from the owner that are recent enough to act on, highest update id seen)."""
    now = now or time.time()
    result = _call(f"https://api.telegram.org/bot{token}/getUpdates?timeout=0&allowed_updates=%5B%22message%22%2C%22callback_query%22%5D").get("result", [])
    last_id = max((u["update_id"] for u in result), default=None)
    mine = []
    for u in result:
        msg = u.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) == str(chat_id) and now - msg.get("date", 0) <= MAX_AGE_SECONDS:
            mine.append(msg)
    return mine, last_id


def apply_tap(data: str, keyboard: list[list[dict]]) -> tuple[list[list[dict]], str] | None:
    """The new keyboard and a toast for one tap, or None if `data` isn't one of ours.

    "a:3"/"s:3" collapse posting 3's button row into a single status button; "u:3" (undo)
    restores the pair. Telegram hands back the message's current keyboard with every tap, so
    the keyboard is the only record needed.
    """
    kind, _, num = data.partition(":")
    if kind not in ("a", "s", "u") or not num.isdigit():
        return None
    pair = [{"text": f"✅ Applied · {num}", "callback_data": f"a:{num}"},
            {"text": f"🚫 Skip · {num}", "callback_data": f"s:{num}"}]
    row = {"a": [{"text": f"✅ Applied {num} · undo", "callback_data": f"u:{num}"}],
           "s": [{"text": f"🚫 Skipped {num} · undo", "callback_data": f"u:{num}"}],
           "u": pair}[kind]
    mine = {f"{p}:{num}" for p in ("a", "s", "u")}
    new, hit = [], False
    for r in keyboard:
        if r and r[0].get("callback_data") in mine:
            new.append(row)
            hit = True
        else:
            new.append(r)
    if not hit:
        return None
    return new, {"a": "Marked applied", "s": "Skipped", "u": "Undone"}[kind]


def pending_taps(token: str, chat_id: str) -> list[dict]:
    """Button taps from the owner's chat."""
    result = _call(f"https://api.telegram.org/bot{token}/getUpdates?timeout=0&allowed_updates=%5B%22callback_query%22%5D").get("result", [])
    taps = []
    for u in result:
        q = u.get("callback_query") or {}
        if str(((q.get("message") or {}).get("chat") or {}).get("id")) == str(chat_id):
            taps.append(q)
    return taps


def handle_tap(token: str, tap: dict) -> None:
    msg = tap["message"]
    keyboard = (msg.get("reply_markup") or {}).get("inline_keyboard") or []
    outcome = apply_tap(tap.get("data") or "", keyboard)
    base = f"https://api.telegram.org/bot{token}"
    if outcome:
        new, toast = outcome
        _call(f"{base}/editMessageReplyMarkup", {
            "chat_id": msg["chat"]["id"], "message_id": msg["message_id"], "reply_markup": {"inline_keyboard": new}})
    else:
        toast = ""
    try:  # an answer to a tap that is minutes old is refused; the edit above is what matters
        _call(f"{base}/answerCallbackQuery", {"callback_query_id": tap["id"], "text": toast})
    except ListenError:
        pass


def confirm(token: str, last_id: int) -> None:
    _call(f"https://api.telegram.org/bot{token}/getUpdates?timeout=0&offset={last_id + 1}")


def reply(token: str, chat_id: str, text: str) -> None:
    _call(f"https://api.telegram.org/bot{token}/sendMessage", {"chat_id": chat_id, "text": text})


def dispatch(repo: str, ref: str, gh_token: str) -> None:
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW}/dispatches"
    req = urllib.request.Request(
        url, data=json.dumps({"ref": ref}).encode(), method="POST",
        headers={"Authorization": f"Bearer {gh_token}", "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28", "Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except urllib.error.HTTPError as exc:
        raise ListenError(f"GitHub dispatch failed (HTTP {exc.code})") from None


def run() -> int:
    token, chat_id = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set", file=sys.stderr)
        return 1
    keywords = load_settings().trigger_keywords

    messages, last_id = pending_messages(token, chat_id)
    if last_id is None:
        print("no pending messages")
        return 0

    for tap in pending_taps(token, chat_id):
        handle_tap(token, tap)

    texts = [m.get("text") for m in messages]
    if any(is_trigger(t, keywords) for t in texts):
        repo, gh_token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_TOKEN")
        if not repo or not gh_token:
            print("GITHUB_REPOSITORY and GITHUB_TOKEN must be set", file=sys.stderr)
            return 1
        dispatch(repo, os.environ.get("GITHUB_REF_NAME") or "main", gh_token)
        reply(token, chat_id, "🔎 On it. Checking every source now; the results land here in a few minutes.")
        print("triggered a run")
    elif any(parse_keyword(t) in ("start", "help") for t in texts):
        reply(token, chat_id, HELP.format(keywords=", ".join(keywords)))
    else:
        print(f"{len(messages)} message(s) from the owner, none a keyword")

    confirm(token, last_id)  # only now, so a failed dispatch is retried next poll
    return 0


def main() -> int:
    try:
        return run()
    except (ListenError, ConfigError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
