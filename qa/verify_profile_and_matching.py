"""Live-API verification for the expanded chat profile + diversified
matching flow (school_or_college/major/vibe/activity_level/
specific_interests_in_mind/hobbies/openness_to_cultural_affinity_groups).

Scripts the test case: "I'm a sophomore in Engineering, want a mix of
professional and fun clubs, not too intense time-wise", followed by one
realistic follow-up answer, calling the real
backend.services.chat_profile.continue_profile_chat and
backend.services.matching.match_clubs_diversified functions directly (no
uvicorn needed — chat_routes.py/matching_routes.py are confirmed thin
pass-throughs with no logic of their own). Prints the full turn-by-turn
conversation trace with profile snapshots, then the final grouped/labeled
club list, and asserts the result is actually diversified across both
requested vibes (not one flat list dominated by a single category) — a
regression check in the same spirit as matching.py's own __main__ assert.

Requires a real ANTHROPIC_API_KEY in .env, like every other __main__/script
in this codebase.

Usage:
    python -m qa.verify_profile_and_matching
"""

from __future__ import annotations

import json

from backend.services.categorize import group_clubs_by_category
from backend.services.chat_profile import continue_profile_chat
from backend.services.matching import match_clubs_diversified


def _print_profile(label: str, profile: dict) -> None:
    print(f"  [{label}] {json.dumps(profile)}")


def main() -> None:
    history: list[dict] = []
    profile: dict = {}

    turn1 = "I'm a sophomore in Engineering, want a mix of professional and fun clubs, not too intense time-wise"
    print("=== Conversation trace ===\n")
    print(f"user: {turn1}")
    history.append({"role": "user", "content": turn1})

    result1 = continue_profile_chat(history, profile=profile)
    if result1.get("error"):
        raise SystemExit(f"Turn 1 failed: {result1['error']}")
    print(f"assistant: {result1['reply']}")
    _print_profile("profile after turn 1", result1["profile"])
    print(f"  ready_for_matching: {result1['ready_for_matching']}")
    assert not result1["ready_for_matching"], (
        "expected turn 1 alone (vibe + activity_level + school, but no "
        "major/specific interest/hobby yet) to NOT clear the low bar - "
        "got ready_for_matching=True unexpectedly"
    )
    profile = result1["profile"]
    history.append({"role": "assistant", "content": result1["reply"]})

    turn2 = "I like robotics and hiking, and I'm interested in consulting or business clubs too"
    print(f"\nuser: {turn2}")
    history.append({"role": "user", "content": turn2})

    result2 = continue_profile_chat(history, profile=profile)
    if result2.get("error"):
        raise SystemExit(f"Turn 2 failed: {result2['error']}")
    print(f"assistant: {result2['reply']}")
    _print_profile("profile after turn 2", result2["profile"])
    print(f"  ready_for_matching: {result2['ready_for_matching']}")
    assert result2["ready_for_matching"], (
        "expected turn 2 (vibe + a major/interest/hobby, 5+ fields filled) "
        "to clear the low bar - two exchanges should be the normal case"
    )
    profile = result2["profile"]

    print("\n=== Final profile used for matching ===")
    print(json.dumps(profile, indent=2))

    matches = match_clubs_diversified(profile, top_k_total=30)
    groups = group_clubs_by_category(matches)

    print("\n=== Matched clubs (grouped by category/vibe) ===")
    for category, clubs in groups.items():
        print(f"\n-- {category} ({len(clubs)}) --")
        for club in clubs:
            matched = club.get("matched_interest", "?")
            print(f"  {club['name']}  (score={club['score']:.3f}, matched_interest={matched!r})")

    represented = [cat for cat in ("Professional", "Social/Fun") if groups.get(cat)]
    assert len(represented) == 2, (
        f"expected both Professional and Social/Fun represented for a "
        f"'both'-vibe profile, got: {list(groups.keys())}"
    )
    print("\nPASS: diversified across both requested vibes")


if __name__ == "__main__":
    main()
