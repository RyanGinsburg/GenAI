"""Group clubs into Professional / Social & Fun / Community Service.

Deliberately NOT an LLM call - the CampusGroups category tags already in
data/clubs_filtered.json's `category` field encode exactly this
distinction (e.g. "PROF: Business and Management", "AFFILIATION: Project
Team" read as career/professional; "Active/Recreational", "Performing
Arts", "Spiritual/Religious" etc. read as social; "Community Service" is
its own explicit tag). A deterministic string match over existing data is
faster, free, and more consistent than asking a model to reclassify text
it's already tagged.
"""

from __future__ import annotations

import json
from pathlib import Path

PROFESSIONAL_MARKERS = (
    "PROF:",
    "AFFILIATION: Project Team",
    "AFFILIATION: Professional Fraternity",
)
COMMUNITY_SERVICE_MARKER = "Community Service"

CATEGORY_ORDER = ["Professional", "Social/Fun", "Community Service"]


def categorize_club(club: dict) -> str:
    """Priority: Professional > Community Service > Social/Fun (catch-all).
    Professional is checked first since PROF:/Project Team/Professional
    Fraternity are the least ambiguous "career-relevant" signals; a club
    that's both professional and service-oriented (e.g. a pre-med
    community-service-heavy professional fraternity) reads more usefully
    under Professional."""
    category = club.get("category") or ""
    if any(marker in category for marker in PROFESSIONAL_MARKERS):
        return "Professional"
    if COMMUNITY_SERVICE_MARKER in category:
        return "Community Service"
    return "Social/Fun"


def group_clubs_by_category(clubs: list[dict]) -> dict[str, list[dict]]:
    """Returns {"Professional": [...], "Social/Fun": [...], "Community Service": [...]},
    each list in the same relative order as the input, omitting empty
    buckets entirely (callers shouldn't render a section with 0 clubs)."""
    groups: dict[str, list[dict]] = {name: [] for name in CATEGORY_ORDER}
    for club in clubs:
        groups[categorize_club(club)].append(club)
    return {name: items for name, items in groups.items() if items}


if __name__ == "__main__":
    clubs_path = Path(__file__).resolve().parent.parent.parent / "data" / "clubs_filtered.json"
    all_clubs = json.loads(clubs_path.read_text())
    counts = {name: 0 for name in CATEGORY_ORDER}
    for c in all_clubs:
        counts[categorize_club(c)] += 1
    print(f"Total clubs: {len(all_clubs)}")
    for name, count in counts.items():
        print(f"  {name}: {count}")
