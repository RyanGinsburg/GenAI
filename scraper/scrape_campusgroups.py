"""Scrape Cornell's public CampusGroups club directory into data/clubs.json.

For each club, collects: name, category, description, website_url. Any field
the directory page doesn't actually provide is written as null rather than
guessed — see CLAUDE.md's "never fabricate" constraint.

How the directory is structured (found by inspecting the live site):
  - https://cornell.campusgroups.com/club_signup lists ~1500 clubs, but the
    unfiltered page (and even its "view all" mode) silently truncates long
    results instead of erroring, so it can't be trusted for a full scrape.
  - The directory itself splits every club into ~12 non-overlapping
    "group_type" buckets (e.g. "Department", "Undergrad General Student
    Organization (GSO)"), shown as filter buttons with counts on the index
    page. Requesting each bucket individually with `view=all` was verified
    (during development, on the smallest and the largest bucket: 6 clubs and
    680 clubs) to return the exact, complete count every time.
  - So this scraper discovers the bucket list from the index page, then
    fetches each bucket's full listing separately. That is also far more
    polite than it sounds: ~13 requests total, not one per club.
  - Each club's name, category, website, and mission/description are all
    already present in that one listing request — no per-club detail page
    fetch is needed.

Usage:
    python scraper/scrape_campusgroups.py                # scrape everything
    python scraper/scrape_campusgroups.py --limit 20      # quick sample run
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://cornell.campusgroups.com/club_signup"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CornellClubAgent/0.1; "
        "student project, contact via github.com/RyanGinsburg/GenAI)"
    )
}
REQUEST_DELAY_SECONDS = 0.75
REQUEST_TIMEOUT_SECONDS = 60
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "clubs.json"

GROUP_TYPE_LINK_RE = re.compile(r"group_type=(\d+)&category_tags=$")

# Cornell's own internal test entry in the directory, not a real club — skip
# its bucket outright rather than filtering it out of the results later.
EXCLUDED_GROUP_TYPE_LABELS = {"Cornell CG TEST"}


def fetch_group_types(session: requests.Session) -> list[dict]:
    """Return every group_type filter bucket on the directory as
    {"id": str, "label": str, "count": int}, smallest bucket first.

    Smallest-first ordering means a --limit sample run only has to download
    small buckets, not the largest one.
    """
    resp = session.get(BASE_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    group_types = []
    for link in soup.select("a.btn.btn-default"):
        match = GROUP_TYPE_LINK_RE.search(link.get("href", ""))
        if not match:
            continue
        badge = link.select_one(".badge")
        count = int(badge.get_text(strip=True)) if badge else 0
        # Direct text children only, so the badge's own "214" isn't included.
        label = "".join(link.find_all(string=True, recursive=False)).strip()
        group_types.append({"id": match.group(1), "label": label, "count": count})

    return sorted(group_types, key=lambda g: g["count"])


def parse_club_card(li) -> dict | None:
    """Extract one club's fields from a <li class="list-group-item"> in the
    listing. Returns None for the header row and any row that isn't a club.

    A small fraction of clubs (membership-closed orgs) render with much
    sparser markup — only a name, no category/website/description block at
    all. Those are still returned, with the missing fields as null.
    """
    if li.get("id") == "list-group-item_header":
        return None

    name_el = li.select_one("h2.media-heading a") or li.select_one("h2.media-heading")
    name = name_el.get_text(strip=True) if name_el else None
    if not name:
        legend = li.select_one("fieldset legend span.sr-only")
        name = legend.get_text(strip=True) if legend else None
    if not name:
        return None

    category = None
    category_el = li.select_one("p.h5.media-heading.grey-element")
    if category_el:
        text = category_el.get_text(separator=" ", strip=True)
        category = re.sub(r"\s+", " ", text).strip(" -") or None

    website_el = li.select_one('a[aria-label="Website"]')
    website_url = website_el.get("href") if website_el else None

    description = None
    mission_el = li.select_one('p[id^="club_"]')
    if mission_el:
        strong = mission_el.find("strong")
        if strong and strong.get_text(strip=True).lower() == "mission":
            strong.extract()
        description = mission_el.get_text(separator=" ", strip=True) or None

    return {
        "name": name,
        "category": category,
        "description": description,
        "website_url": website_url,
    }


def fetch_clubs_for_group_type(session: requests.Session, group_type_id: str) -> list[dict]:
    """Fetch and parse every club in one group_type bucket (view=all)."""
    resp = session.get(
        BASE_URL,
        params={"view": "all", "group_type": group_type_id, "category_tags": ""},
        headers=HEADERS,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return [
        club
        for li in soup.select("li.list-group-item")
        if (club := parse_club_card(li)) is not None
    ]


def scrape_all(limit: int | None = None, delay: float = REQUEST_DELAY_SECONDS) -> list[dict]:
    """Scrape the full directory, or stop early once `limit` clubs are collected."""
    session = requests.Session()
    group_types = fetch_group_types(session)
    total_expected = sum(g["count"] for g in group_types)
    print(f"Found {len(group_types)} group_type categories, {total_expected} clubs total")

    all_clubs: list[dict] = []
    for gt in group_types:
        if gt["count"] == 0 or gt["label"] in EXCLUDED_GROUP_TYPE_LABELS:
            continue
        if limit is not None and len(all_clubs) >= limit:
            break

        print(f"Scraping '{gt['label']}' ({gt['count']} clubs)...")
        clubs = fetch_clubs_for_group_type(session, gt["id"])
        all_clubs.extend(clubs)
        print(f"  -> got {len(clubs)} (running total: {len(all_clubs)})")
        time.sleep(delay)

    if limit is not None:
        all_clubs = all_clubs[:limit]
    return all_clubs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Stop after collecting this many clubs (for a quick sample run)",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Where to write the JSON output (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    clubs = scrape_all(limit=args.limit)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(clubs, indent=2, ensure_ascii=False))
    print(f"\nWrote {len(clubs)} clubs to {args.output}")


if __name__ == "__main__":
    main()
