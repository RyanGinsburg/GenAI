""""Saved Chats": a logged-in user's saved conversation/match-result
snapshots, shown as a second view inside "My Clubs" alongside saved
clubs.

Unlike saved_clubs.py (which stores only a pointer and resolves details
from clubs_filtered.json at read time), a saved chat stores its full
profile + grouped-results JSON directly - see db.py's module docstring
for why (a saved chat is a point-in-time result that can't be
regenerated later from club data alone).
"""

from __future__ import annotations

import json
from datetime import datetime

from backend import db


def _auto_label(profile: dict | None) -> str:
    """Falls back to a bare date when the profile has nothing to name it
    by; otherwise leads with the vibe for a more useful label at a
    glance, e.g. "Professional search - Sep 11, 2026"."""
    date_str = datetime.now().strftime("%b %d, %Y")
    vibe = (profile or {}).get("vibe")
    if vibe:
        return f"{vibe.capitalize()} search - {date_str}"
    return f"Chat from {date_str}"


def save_chat(user_id: int, profile: dict, groups: dict, label: str | None = None) -> dict:
    """Saves a snapshot of the given profile/groups. Returns the fresh
    list (list_saved_chats shape) so callers can render the update
    without a second round trip."""
    chat_id = db.add_saved_chat(
        user_id,
        label or _auto_label(profile),
        json.dumps(profile or {}),
        json.dumps(groups or {}),
    )
    return {"id": chat_id, "chats": list_saved_chats(user_id)}


def list_saved_chats(user_id: int) -> list[dict]:
    """[{"id", "label", "created_at"}, ...], most recent first - list view
    only, no profile/groups payload (see get_saved_chat_detail)."""
    return db.list_saved_chats(user_id)


def get_saved_chat_detail(user_id: int, chat_id: int) -> dict | None:
    """Full {"id", "label", "created_at", "profile", "groups"} with the
    stored JSON parsed back into dicts, or None if not found/not owned."""
    row = db.get_saved_chat(user_id, chat_id)
    if row is None:
        return None
    return {
        "id": row["id"],
        "label": row["label"],
        "created_at": row["created_at"],
        "profile": json.loads(row["profile_json"]),
        "groups": json.loads(row["groups_json"]),
    }


def remove_saved_chat(user_id: int, chat_id: int) -> None:
    db.remove_saved_chat(user_id, chat_id)
