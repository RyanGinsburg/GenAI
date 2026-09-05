"""Filter data/clubs.json down to undergrad-facing student organizations,
written to data/clubs_filtered.json. data/clubs.json itself is left
untouched -- this is a separate, derived file.

Why: data/clubs.json has 1521 real CampusGroups entries, but CampusGroups
treats "club" broadly -- it also includes academic departments, grad/
professional student orgs, off-campus housing companies, dorm/house-system
groups, and social Greek life, none of which are what an undergrad asking
"what club should I join" is looking for. Matching and researching all 1521
wastes research_agent.py calls on dead/irrelevant sites and dilutes
match_clubs results. See CLAUDE.md's "Idea raised, not yet acted on" note
-- this makes that call, with an explicit go-ahead.

Every CampusGroups club falls into one of these top-level category prefixes
(the part of `category` before the first " - "):

    KEPT
      Undergrad General Student Organization (GSO)   680 clubs
      Undergrad University Student Organization (USO) 197 clubs

    EXCLUDED
      Department                                       215  -- academic
        departments/programs, not student-run clubs
      Grad/Professional General Student Organization (GSO) 120 -- grad clubs
      Grad/Professional University Student Organization (USO) 181 -- grad clubs
      Sorority & Fraternity Student Organization (SFSO) 48  -- social Greek
        life (separate rush/recruitment system this app doesn't model)
      Off-Campus Housing Company                        47  -- housing, not
        a club
      Housing and Residence Life                        27  -- dorm-related
      West Campus House System                           6  -- dorm-related

Two decisions worth calling out explicitly (confirmed with the project owner
2026-09-05):
  - "Professional fraternities" (e.g. Alpha Kappa Psi, Phi Alpha Delta) are
    tagged with an "AFFILIATION: Professional Fraternity (PFC)" sub-tag but
    fall under the Undergrad GSO/USO prefixes, not SFSO -- so they're KEPT.
    They function as career-focused clubs with real recruitment cycles
    (Alpha Kappa Psi was already one of research_agent.py's QA test cases),
    unlike social Greek life.
  - There is no NCAA/varsity/club-sports category in this data at all --
    Cornell varsity athletics isn't run through CampusGroups. The closest
    thing, an "Active/Recreational: Competitive" sub-tag on ordinary
    Undergrad GSO/USO clubs (mostly student-run club sports teams), is KEPT
    since those are legitimate student clubs, not NCAA teams.

Usage:
    python scraper/filter_clubs.py
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
INPUT_PATH = DATA_DIR / "clubs.json"
OUTPUT_PATH = DATA_DIR / "clubs_filtered.json"

KEEP_PREFIXES = (
    "Undergrad General Student Organization (GSO)",
    "Undergrad University Student Organization (USO)",
)


def is_undergrad_org(category: str | None) -> bool:
    """True iff a club's top-level category (the part before " - ") is one
    of the undergrad student-org prefixes this app targets."""
    if not category:
        return False
    prefix = category.split(" - ")[0]
    return prefix in KEEP_PREFIXES


def filter_clubs(clubs: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """Split clubs into (kept, excluded_counts_by_prefix)."""
    kept = []
    excluded_counts: dict[str, int] = {}
    for club in clubs:
        if is_undergrad_org(club.get("category")):
            kept.append(club)
        else:
            prefix = (club.get("category") or "(no category)").split(" - ")[0]
            excluded_counts[prefix] = excluded_counts.get(prefix, 0) + 1
    return kept, excluded_counts


def main() -> None:
    clubs = json.loads(INPUT_PATH.read_text())
    kept, excluded_counts = filter_clubs(clubs)

    OUTPUT_PATH.write_text(json.dumps(kept, indent=2))

    print(f"Read {len(clubs)} clubs from {INPUT_PATH}")
    print(f"Kept {len(kept)} undergrad student orgs -> {OUTPUT_PATH}")
    print(f"Excluded {len(clubs) - len(kept)}:")
    for prefix, n in sorted(excluded_counts.items(), key=lambda x: -x[1]):
        print(f"  {n:4d}  {prefix}")


if __name__ == "__main__":
    main()
