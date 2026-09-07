"""Single source of truth for the student profile shape shared across
chat_profile.py (produces/updates it), matching.py (consumes it),
matching_routes.py (validates it over the wire), and chat_routes.py
(threads it through /chat/message). Previously this shape was duplicated
across four places with no shared type (mode vs. vibe, a flat interests
list vs. named fields) - a field rename/addition now happens in exactly
one place.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

PROFILE_FIELDS = (
    "school_or_college",
    "major",
    "vibe",
    "activity_level",
    "specific_interests_in_mind",
    "hobbies",
    "openness_to_cultural_affinity_groups",
)
LIST_FIELDS = ("specific_interests_in_mind", "hobbies")
MAX_LIST_ITEMS = 8


class StudentProfile(BaseModel):
    school_or_college: Optional[str] = None
    major: Optional[str] = None
    vibe: Optional[Literal["social", "professional", "both"]] = None
    activity_level: Optional[Literal["low", "medium", "high"]] = None
    specific_interests_in_mind: list[str] = Field(default_factory=list)
    hobbies: list[str] = Field(default_factory=list)
    openness_to_cultural_affinity_groups: Optional[Literal["yes", "open", "not_sure"]] = None


def merge_profile(old: dict | None, delta: dict | None) -> dict:
    """Deterministic merge - the one place "merge, don't discard" is
    actually enforced in code, not just prompt text. Any non-null field in
    `delta` overwrites `old`; anything delta omits/nulls is left untouched.
    List fields are wholesale-replaced, not appended - callers (the LLM,
    via the system prompt) are instructed to send the FULL updated list
    whenever they touch that field at all, so uniform non-null-overwrite
    semantics work for every field, initial interview or refine alike.
    List fields are capped to the most recent MAX_LIST_ITEMS to bound
    multi-query matching cost."""
    merged = dict(old or {})
    for key in PROFILE_FIELDS:
        if delta and key in delta and delta[key] is not None:
            value = delta[key]
            if key in LIST_FIELDS and isinstance(value, list):
                value = value[-MAX_LIST_ITEMS:]
            merged[key] = value
    return merged


def is_ready_for_matching(profile: dict) -> bool:
    """Deterministic, explicit low bar: enough to search as soon as we
    know the general vibe AND at least one concrete topic (a major, a
    named interest, or a hobby) - never require every field. This backs
    up (and can force past) the model's own ready_for_matching judgment so
    "two exchanges should be the normal case" is actually enforced, not
    just prompt-hoped-for."""
    profile = profile or {}
    has_vibe = bool(profile.get("vibe"))
    has_topic = bool(
        profile.get("major")
        or profile.get("specific_interests_in_mind")
        or profile.get("hobbies")
    )
    filled = sum(1 for f in PROFILE_FIELDS if profile.get(f))
    return has_vibe and has_topic and filled >= 3
