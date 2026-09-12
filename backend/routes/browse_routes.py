"""GET /clubs — manually search/filter the full 877-club directory.
GET /clubs/ai-search — semantic ("understands meaning") search over the
same directory, for queries like "find my cs clubs" that plain substring
matching can't handle (the club has to be literally named/described with
the search term today; ai-search matches on meaning instead).

No auth needed (browsing is anonymous per the product decision). No
research_agent call here either - browsing only ever returns the same
name/category/description/website_url shape as everywhere else in this
app; getting a specific club's deadlines is always a separate, explicit
POST /research.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from backend.services.ai_search import expand_search_query
from backend.services.categorize import CATEGORY_ORDER, categorize_club
from backend.services.matching import load_clubs, match_clubs

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


@router.get("/clubs/ai-search")
def ai_search_clubs(
    q: str = Query(..., min_length=1),
    category: str = Query(default="All"),
    top_k: int = Query(default=24, ge=1, le=60),
):
    """Semantic search via matching.match_clubs() - a fixed top-K ranked
    list, not a paginated set (unlike /clubs above): "page 2 of semantic
    similarity" isn't a meaningful thing for a user to ask for the way
    "page 2 of substring matches" is, so this deliberately returns no
    total/page/page_size fields at all.

    The raw query is expanded first (expand_search_query) - bare
    abbreviations like "cs" don't embed anywhere near "computer science"
    with the local model, so a quick Claude call rewrites the query into
    clearer language before it's embedded. See ai_search.py's docstring
    for the empirical case this fixes.

    When a category filter is active, over-fetches (top_k * 3) before
    filtering, since match_clubs() has no category awareness of its own
    and a plain top_k slice could otherwise come back short after
    filtering - same over-fetch-then-trim idea match_clubs_diversified()
    already uses in matching.py.
    """
    fetch_k = top_k * 3 if category != "All" else top_k
    expanded_q = expand_search_query(q)
    results = match_clubs(expanded_q, top_k=fetch_k)

    if category != "All" and category in CATEGORY_ORDER:
        results = [c for c in results if categorize_club(c) == category]
    results = results[:top_k]

    return {
        "clubs": results,
        "query": q,
        "categories": ["All", *CATEGORY_ORDER],
    }
