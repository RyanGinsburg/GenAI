"""A small on-disk cache in front of research_agent.research_club().

Why: research_club() fetches a page with a headless browser and calls the
Claude API - real latency and real cost per call. A club's deadline/meeting
info doesn't change minute to minute, so re-doing that work every time any
student matches to the same club (which will happen constantly once
matching runs against a shared 877-club set) is pure waste. This mirrors
the pattern matching.py already uses for embeddings.npy: a flat on-disk
cache, keyed by the thing that determines the result, with an expiry
instead of a content hash (a club's website isn't re-scraped to check for
changes here, so we just treat entries as stale after TTL_SECONDS and
re-fetch).

Deliberately NOT part of research_agent.py itself: research_club() stays a
pure "go find out" function with no caching/storage concerns; this module
is the route-level policy of when to actually call it.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "research_cache.json"
TTL_SECONDS = 24 * 60 * 60  # 24 hours


def _load() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}  # corrupt/unreadable cache -> treat as empty rather than crash


def _save(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def get_cached(website_url: str) -> dict | None:
    """Return the cached research_club() result for website_url if present
    and still fresh, else None."""
    entry = _load().get(website_url)
    if entry is None:
        return None
    if time.time() - entry["cached_at"] > TTL_SECONDS:
        return None
    return entry["result"]


def set_cached(website_url: str, result: dict) -> None:
    """Store result for website_url, timestamped now."""
    cache = _load()
    cache[website_url] = {"result": result, "cached_at": time.time()}
    _save(cache)
