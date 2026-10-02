"""Notification channels. Add a new channel by subclassing Notifier."""
from __future__ import annotations

import argparse
import os
import sys
from abc import ABC, abstractmethod

import requests
from dotenv import load_dotenv

TELEGRAM_MAX_LEN = 4096


class NotifierError(RuntimeError):
    pass


class Notifier(ABC):
    @abstractmethod
    def send(self, text: str) -> None:
        """Send a message, raising NotifierError on failure."""


class TelegramNotifier(Notifier):
    def __init__(self, token: str, chat_id: str, timeout: float = 15):
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout

    @classmethod
    def from_env(cls) -> "TelegramNotifier":
        load_dotenv()
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        missing = [
            name
            for name, val in (("TELEGRAM_BOT_TOKEN", token), ("TELEGRAM_CHAT_ID", chat_id))
            if not val
        ]
        if missing:
            raise NotifierError(f"Missing environment variables: {', '.join(missing)}")
        return cls(token, chat_id)

    def send(self, text: str) -> None:
        if len(text) > TELEGRAM_MAX_LEN:
            raise NotifierError(f"Message too long ({len(text)} > {TELEGRAM_MAX_LEN})")
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            resp = requests.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "disable_web_page_preview": True,
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            # Don't chain the original: its message can contain the token-bearing URL.
            raise NotifierError(f"Telegram request failed: {type(exc).__name__}") from None
        if not resp.ok:
            try:
                detail = resp.json().get("description", "")
            except ValueError:
                detail = ""
            raise NotifierError(f"Telegram error {resp.status_code}: {detail}")


def get_chat_id() -> None:
    """Print chat IDs from recent messages sent to the bot."""
    load_dotenv()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise NotifierError("TELEGRAM_BOT_TOKEN is not set")
    resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15)
    if not resp.ok:
        raise NotifierError(f"Telegram error {resp.status_code}")
    chats = {
        u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name", "")
        for u in resp.json().get("result", [])
        if "message" in u
    }
    if not chats:
        print("No messages found. Send your bot a message in Telegram, then retry.")
    for chat_id, name in chats.items():
        print(f"chat id: {chat_id}  ({name})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Notifier smoke test")
    parser.add_argument("--get-chat-id", action="store_true", help="print your chat ID")
    args = parser.parse_args()
    try:
        if args.get_chat_id:
            get_chat_id()
        else:
            TelegramNotifier.from_env().send("hello")
            print("Sent.")
    except NotifierError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
