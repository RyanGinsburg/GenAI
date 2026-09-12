"""Verification for the saved_chats backend (db.py / services/saved_chats.py)
added alongside the "Save chat" feature.

Runs entirely against a throwaway SQLite file (backend.db.DB_PATH is
monkeypatched before anything touches the database), so it never reads or
writes the real dev data/app.db. Checks round-trip fidelity of the saved
profile/groups JSON, that ownership is scoped per-user (one user can't
read or delete another user's saved chat by id), and that listing order
is most-recent-first.

Usage:
    python -m qa.verify_saved_chats
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import backend.db as db

with tempfile.TemporaryDirectory() as tmp_dir:
    db.DB_PATH = Path(tmp_dir) / "test_app.db"
    db.init_db()

    from backend.services import saved_chats
    from backend.services.auth import hash_password

    def make_user(email: str) -> int:
        return db.create_user(f"Test User {email}", email, hash_password("throwaway-password"))

    def main() -> None:
        print("=== verify_saved_chats ===")

        alice = make_user("alice@example.com")
        bob = make_user("bob@example.com")

        profile = {"vibe": "social", "hobbies": ["skiing", "spikeball"]}
        groups = {"Social/Fun": [{"name": "Cornell Roundnet", "match_percent": 97}]}

        result = saved_chats.save_chat(alice, profile, groups)
        chat_id = result["id"]
        print(f"  saved chat id={chat_id} for alice")

        # Round-trip fidelity.
        detail = saved_chats.get_saved_chat_detail(alice, chat_id)
        assert detail is not None, "expected to read back the just-saved chat"
        assert detail["profile"] == profile, "profile did not round-trip exactly"
        assert detail["groups"] == groups, "groups did not round-trip exactly"
        print("  PASS: profile/groups round-trip exactly")

        # Ownership scoping: bob can't read or delete alice's chat by id.
        assert saved_chats.get_saved_chat_detail(bob, chat_id) is None, (
            "expected another user's get_saved_chat_detail to return None"
        )
        saved_chats.remove_saved_chat(bob, chat_id)
        assert saved_chats.get_saved_chat_detail(alice, chat_id) is not None, (
            "bob's remove call should not have deleted alice's chat"
        )
        print("  PASS: ownership scoping holds for read and delete")

        # Most-recent-first ordering.
        second_id = saved_chats.save_chat(alice, {"vibe": "professional"}, {})["id"]
        listing = saved_chats.list_saved_chats(alice)
        assert [c["id"] for c in listing][:2] == [second_id, chat_id], (
            f"expected most-recent-first ordering, got {json.dumps(listing)}"
        )
        assert "profile_json" not in listing[0] and "groups" not in listing[0], (
            "list view should omit the heavy profile/groups payload"
        )
        print("  PASS: most-recent-first ordering, list view omits payload")

        # Removal actually removes it.
        saved_chats.remove_saved_chat(alice, chat_id)
        assert saved_chats.get_saved_chat_detail(alice, chat_id) is None, "expected chat to be gone after removal"
        print("  PASS: removal round-trips")

        print("\nPASS: saved_chats backend verified")

    main()
