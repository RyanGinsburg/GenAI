""""My Clubs": a logged-in user's saved-club list.

SQLite (db.py) stores only (user_id, website_url, saved_at) - deliberately
denormalized. Full club details (name/description/category) are resolved
from data/clubs_filtered.json at read time via matching.load_clubs(), so
there's one source of truth for club data and saved_clubs never goes
stale relative to it.
"""

from __future__ import annotations

from backend import db
from backend.services.matching import load_clubs


def save_club(user_id: int, website_url: str) -> None:
    db.add_saved_club(user_id, website_url)


def unsave_club(user_id: int, website_url: str) -> None:
    db.remove_saved_club(user_id, website_url)


def get_saved_clubs_with_details(user_id: int) -> list[dict]:
    """Most-recently-saved first. If a saved website_url is no longer in
    the current clubs_filtered.json snapshot (directory changed since it
    was saved), it's silently skipped rather than shown as a broken stub."""
    saved = db.list_saved_clubs(user_id)
    if not saved:
        return []

    saved_urls_in_order = [row["website_url"] for row in saved]
    clubs_by_url = {c["website_url"]: c for c in load_clubs()}

    return [clubs_by_url[url] for url in saved_urls_in_order if url in clubs_by_url]
