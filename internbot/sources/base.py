from __future__ import annotations

import logging
import re
import time

import requests

from internbot.textutil import normalize_text

log = logging.getLogger(__name__)


class SourceError(RuntimeError):
    """A job source failed. Messages must never contain URLs (they can carry credentials)."""


def get_json(url: str, params: dict | None = None, timeout: float = 20, retries: int = 3):
    """GET and decode JSON, retrying timeouts, connection errors and 5xx responses."""
    last = "unknown error"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
        except requests.RequestException as exc:
            last = type(exc).__name__
        else:
            if resp.ok:
                try:
                    return resp.json()
                except ValueError:
                    raise SourceError("response was not valid JSON") from None
            last = f"HTTP {resp.status_code}"
            if resp.status_code < 500 and resp.status_code != 429:
                break  # client error: retrying won't help
        if attempt < retries:
            time.sleep(2 ** (attempt - 1))
    raise SourceError(f"request failed ({last})")


def location_matcher(keywords: list[str]):
    """Build a predicate matching whole-word, accent-insensitive location keywords."""
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(normalize_text(k)) for k in keywords) + r")\b"
    )
    return lambda text: bool(pattern.search(normalize_text(text or "")))
