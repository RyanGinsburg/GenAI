"""GET /clubs — manually search/filter the full 877-club directory.

No auth needed (browsing is anonymous per the product decision). No
research_agent call here either - browsing only ever returns the same
name/category/description/website_url shape as everywhere else in this
app; getting a specific club's deadlines is always a separate, explicit
POST /research.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.services.categorize import CATEGORY_ORDER, categorize_club
from backend.services.matching import load_clubs

router = APIRouter()

PAGE_SIZE = 24


def _search_priority(club: dict, search: str) -> int:
    """Rank a substring match by where the hit occurs, so a club whose name
    or category is actually about the query term outranks one where the
    term just happens to appear once in a longer description. Bug this
    fixes: searching "law" put Cornell Real Estate Club first (its
    description lists "hospitality, law, architecture..." among the
    disciplines it draws on) ahead of every real law-focused club, because
    the plain substring filter had no relevance ordering at all - it just
    returned matches in clubs_filtered.json's original order."""
    if search in (club.get("name") or "").lower():
        return 0
    if search in (club.get("category") or "").lower():
        return 1
    return 2


@router.get("/clubs")
def browse_clubs(
    search: str = Query(default=""),
    category: str = Query(default="All"),
    page: int = Query(default=1, ge=1),
):
    clubs = load_clubs()

    if category != "All" and category in CATEGORY_ORDER:
        clubs = [c for c in clubs if categorize_club(c) == category]

    search = search.strip().lower()
    if search:
        clubs = [
            c
            for c in clubs
            if search in (c.get("name") or "").lower()
            or search in (c.get("description") or "").lower()
            or search in (c.get("category") or "").lower()
        ]
        # Stable sort: same-priority matches keep their original relative order.
        clubs.sort(key=lambda c: _search_priority(c, search))

    total = len(clubs)
    start = (page - 1) * PAGE_SIZE
    page_clubs = clubs[start : start + PAGE_SIZE]

    return {
        "clubs": page_clubs,
        "total": total,
        "page": page,
        "page_size": PAGE_SIZE,
        "categories": ["All", *CATEGORY_ORDER],
    }
