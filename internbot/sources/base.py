from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, NamedTuple, TypeVar

import requests

from internbot import places

log = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")

# A few career sites answer an empty User-Agent with a challenge page.
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
}


class SourceError(RuntimeError):
    """A job source failed. Messages must never contain URLs (they can carry credentials)."""


class Posting(NamedTuple):
    """An apply URL a feed told us about, plus the employer's display name when known.

    Feeds are mined for these because an apply URL names the employer's ATS board:
    `job-boards.greenhouse.io/figureai/jobs/1` means `figureai` is a Greenhouse board.
    """

    url: str
    company: str = ""


class FeedResult(NamedTuple):
    jobs: list
    postings: list[Posting]


def _send(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    body: object = None,
    headers: dict | None = None,
    timeout: float = 20,
    retries: int = 3,
):
    """Send a request, retrying timeouts, connection errors, 429 and 5xx responses."""
    last = "unknown error"
    send = requests.post if method == "POST" else requests.get
    merged = {**DEFAULT_HEADERS, **(headers or {})}
    for attempt in range(1, retries + 1):
        try:
            if method == "POST":
                resp = send(url, params=params, json=body, headers=merged, timeout=timeout)
            else:
                resp = send(url, params=params, headers=merged, timeout=timeout)
        except requests.RequestException as exc:
            last = type(exc).__name__
        else:
            if resp.ok:
                return resp
            last = f"HTTP {resp.status_code}"
            if resp.status_code < 500 and resp.status_code != 429:
                break  # client error: retrying won't help
        if attempt < retries:
            time.sleep(2 ** (attempt - 1))
    raise SourceError(f"request failed ({last})")


def _json(resp):
    try:
        return resp.json()
    except ValueError:
        raise SourceError("response was not valid JSON") from None


def get_json(
    url: str, params: dict | None = None, timeout: float = 20, retries: int = 3, headers: dict | None = None
):
    """GET and decode JSON."""
    return _json(_send("GET", url, params=params, headers=headers, timeout=timeout, retries=retries))


def post_json(url: str, body: object, timeout: float = 20, retries: int = 1, headers: dict | None = None):
    """POST a JSON body and decode the JSON reply."""
    return _json(
        _send("POST", url, body=body, headers={"Accept": "application/json", **(headers or {})},
              timeout=timeout, retries=retries)
    )


def get_text(url: str, params: dict | None = None, timeout: float = 20, retries: int = 1, headers: dict | None = None) -> str:
    return _send("GET", url, params=params, headers=headers, timeout=timeout, retries=retries).text


def parallel_map(
    items: Iterable[T],
    fn: Callable[[T], R],
    workers: int = 16,
    deadline: float | None = None,
) -> list[R | None]:
    """Run `fn` over `items` with bounded concurrency. A task that raises (dead board, 404,
    rate limit) or starts after `deadline` (a time.monotonic() value) yields None, so one bad
    board can't lose the others and a slow stage can't run the whole job out of time."""
    items = list(items)
    if not items:
        return []

    def run(item: T) -> R | None:
        if deadline is not None and time.monotonic() > deadline:
            return None
        try:
            return fn(item)
        except Exception as exc:  # noqa: BLE001 - a board failing must never crash the run
            log.debug("task failed: %s", type(exc).__name__)
            return None

    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(items)))) as pool:
        return list(pool.map(run, items))


def flatten(results: Iterable[list | None]) -> tuple[list, int]:
    """Concatenate per-board result lists, dropping duplicate URLs. Returns (jobs, boards_reachable)."""
    seen: set[str] = set()
    jobs: list = []
    reachable = 0
    for lst in results:
        if lst is None:
            continue
        reachable += 1
        for job in lst:
            if job.url in seen:
                continue
            seen.add(job.url)
            jobs.append(job)
    return jobs, reachable


def location_matcher(keywords: list[str], remote_canada: bool = True):
    """Predicate for "is this location in the Montreal area": the configured keywords
    (whole-word, accent-insensitive), the Montreal suburbs, and remote-in-Canada."""
    return places.make_matcher(keywords, remote_canada)
