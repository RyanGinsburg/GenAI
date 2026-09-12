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

Also runs three smaller checks: verify_social_needs_a_topic() (a
social-leaning profile shouldn't be ready with only a major, per the
tightened is_ready_for_matching() rule, deterministic/no LLM call),
verify_hobby_match_percent() (a direct hobby match, e.g.
"skiing"/"spikeball", should come back with a high match_percent through
the full match_clubs_diversified path), and
verify_judge_pushes_back_on_vague_answers() (a live-LLM regression test
for chat_profile.py's judge/ask split - a generic "sports and stuff"
answer that would have cleared the OLD deterministic-only floor must
still be held back by the judge, converging to ready only once real
specifics are given).

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
from backend.services.profile_schema import is_ready_for_matching


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
        "expected the judge to consider this specific enough after 2 turns "
        "(three named interests: robotics, hiking, consulting/business) - "
        "if this now flakes, the turn 2 answer may need one more concrete "
        "detail, or MAX_TURNS may need revisiting. Readiness is now a live "
        "judge call, not a guaranteed self-report, so occasional flakiness "
        "here is informative rather than a hard regression signal on its own."
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


def verify_social_needs_a_topic() -> None:
    """The tightened is_ready_for_matching() should hold a social-leaning
    profile back until it has a real hobby/interest, not just a major -
    exercises the vibe-specific rule added to profile_schema.py."""
    print("\n=== verify_social_needs_a_topic ===")
    major_only = {
        "school_or_college": "Arts and Sciences",
        "major": "Computer Science",
        "vibe": "social",
        "activity_level": "medium",
    }
    print(f"  major-only social profile: {json.dumps(major_only)}")
    assert not is_ready_for_matching(major_only), (
        "a social vibe with only a major (no hobby/interest) should NOT "
        "be ready - a major alone says nothing about social preferences"
    )
    print("  PASS: not ready without a hobby/interest")

    with_hobby = {**major_only, "hobbies": ["board games"]}
    print(f"  + a hobby: {json.dumps(with_hobby)}")
    assert is_ready_for_matching(with_hobby), "adding a hobby should clear the bar"
    print("  PASS: ready once a hobby is added")


def verify_hobby_match_percent() -> None:
    """End-to-end regression for the keyword-bonus/match_percent fix:
    direct hobby matches (skiing, spikeball) should come back with a high
    displayed confidence, not read as mediocre - verified through the
    full profile -> match_clubs_diversified path, not just the low-level
    function (matching.py's own __main__ covers that)."""
    print("\n=== verify_hobby_match_percent ===")
    profile = {
        "vibe": "social",
        "activity_level": "medium",
        "hobbies": ["skiing", "spikeball"],
    }
    matches = match_clubs_diversified(profile, top_k_total=30)

    ski_hit = next((c for c in matches if "ski" in c["name"].lower()), None)
    assert ski_hit is not None, "expected a ski club among the results for hobby 'skiing'"
    print(f"  {ski_hit['name']!r} -> {ski_hit['match_percent']}%")
    assert ski_hit["match_percent"] >= 80, f"expected >=80%, got {ski_hit['match_percent']}"

    roundnet_hit = next((c for c in matches if c["name"] == "Cornell Roundnet"), None)
    assert roundnet_hit is not None, "expected Cornell Roundnet among the results for hobby 'spikeball'"
    print(f"  Cornell Roundnet -> {roundnet_hit['match_percent']}%")
    assert roundnet_hit["match_percent"] >= 80, f"expected >=80%, got {roundnet_hit['match_percent']}"

    print("PASS: direct hobby matches score with high confidence")


def verify_judge_pushes_back_on_vague_answers() -> None:
    """Direct regression test for the exact complaint the judge/ask split
    fixes: a generic, one-word-per-field answer used to be able to clear
    the old single-call self-report after as little as one follow-up.
    Turn 2 here fills 4+ fields (school, major, vibe, activity_level) and
    includes a topic-shaped word ("sports") - enough to have cleared the
    OLD deterministic floor alone - but is qualitatively generic. The
    judge should hold it back until real specifics come out."""
    print("\n=== verify_judge_pushes_back_on_vague_answers ===")
    history: list[dict] = []
    profile: dict = {}

    turn1 = "hi, I want a fun club"
    print(f"user: {turn1}")
    history.append({"role": "user", "content": turn1})
    result = continue_profile_chat(history, profile=profile)
    if result.get("error"):
        raise SystemExit(f"Turn 1 failed: {result['error']}")
    print(f"assistant: {result['reply']}")
    _print_profile("profile after turn 1", result["profile"])
    assert not result["ready_for_matching"], "turn 1 alone should never be ready"
    profile = result["profile"]
    history.append({"role": "assistant", "content": result["reply"]})

    turn2 = (
        "I like sports and stuff, and I'm in Arts and Sciences majoring in "
        "Government, want something social, not too much of a time commitment"
    )
    print(f"\nuser: {turn2}")
    history.append({"role": "user", "content": turn2})
    result = continue_profile_chat(history, profile=profile)
    if result.get("error"):
        raise SystemExit(f"Turn 2 failed: {result['error']}")
    print(f"assistant: {result['reply']}")
    _print_profile("profile after turn 2", result["profile"])
    print(f"  ready_for_matching: {result['ready_for_matching']}")
    assert not result["ready_for_matching"], (
        "expected the judge to push back on a generic 'sports and stuff' "
        "answer even though it fills enough fields to have cleared the old "
        "deterministic-only floor - this is the direct fix for the user's "
        "complaint of the interview ending after only ~2 shallow answers"
    )
    print("  PASS: judge correctly did NOT accept a vague answer as sufficient")
    profile = result["profile"]
    history.append({"role": "assistant", "content": result["reply"]})

    turn3 = (
        "I mean I play pickup basketball a couple times a week, and I'm also "
        "really into board games, I go to game nights when I can"
    )
    print(f"\nuser: {turn3}")
    history.append({"role": "user", "content": turn3})
    result = continue_profile_chat(history, profile=profile)
    if result.get("error"):
        raise SystemExit(f"Turn 3 failed: {result['error']}")
    print(f"assistant: {result['reply']}")
    _print_profile("profile after turn 3", result["profile"])
    print(f"  ready_for_matching: {result['ready_for_matching']}")
    assert result["ready_for_matching"], (
        "expected concrete follow-up specifics (pickup basketball, board "
        "game nights) to satisfy the judge within a couple more turns, well "
        f"inside MAX_TURNS - got ready_for_matching=False on turn 3"
    )
    print("  PASS: judge accepted the profile once real specifics were given")


if __name__ == "__main__":
    main()
    verify_social_needs_a_topic()
    verify_hobby_match_percent()
    verify_judge_pushes_back_on_vague_answers()
