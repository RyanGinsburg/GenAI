"""Live-API verification for Browse Clubs' "search by meaning" AI search
(backend/services/ai_search.py + the /clubs/ai-search route logic in
backend/routes/browse_routes.py).

Calls the route function directly (no uvicorn needed - routes in this
codebase are confirmed thin pass-throughs), using the user's own literal
example query, "find my cs clubs" - a bare-abbreviation query that plain
substring search and even raw (unexpanded) embedding search both fail on
(spot-checked live: match_clubs("find my cs clubs") alone surfaces "Club
Sports Council" first and never puts a real CS club in its top 10,
because "cs" doesn't embed near "computer science" with this local
model). Confirms query expansion fixes this, and that category filtering
still works after the fix.

Requires a real ANTHROPIC_API_KEY in .env (ai_search.py makes a live
Claude call) and the local sentence-transformers model/embeddings cache
already built by matching.py.

Usage:
    python -m qa.verify_ai_search
"""

from __future__ import annotations

from backend.routes.browse_routes import ai_search_clubs

CS_CLUB_NAME = "Association of Computer Science Undergraduates"


def verify_abbreviation_query_finds_real_cs_club() -> None:
    print("=== verify_abbreviation_query_finds_real_cs_club ===")
    result = ai_search_clubs(q="find my cs clubs", category="All", top_k=10)
    names = [c["name"] for c in result["clubs"]]
    print(f"  top results: {names[:5]}")
    assert CS_CLUB_NAME in names[:5], (
        f"expected {CS_CLUB_NAME!r} in the top 5 results for a bare-abbreviation "
        f"CS query, got: {names[:5]}"
    )
    print(f"  PASS: {CS_CLUB_NAME!r} found in the top 5")


def verify_category_filter_still_applies() -> None:
    print("\n=== verify_category_filter_still_applies ===")
    result = ai_search_clubs(q="find my cs clubs", category="Social/Fun", top_k=10)
    from backend.services.categorize import categorize_club

    bad = [c["name"] for c in result["clubs"] if categorize_club(c) != "Social/Fun"]
    assert not bad, f"expected every result to be categorized Social/Fun, got these that aren't: {bad}"
    print(f"  PASS: all {len(result['clubs'])} results are genuinely Social/Fun")


def verify_query_field_is_the_original_raw_query() -> None:
    print("\n=== verify_query_field_is_the_original_raw_query ===")
    result = ai_search_clubs(q="find my cs clubs", category="All", top_k=5)
    assert result["query"] == "find my cs clubs", (
        f"expected the response's 'query' field to echo the user's raw input "
        f"(not the internally-expanded phrase), got {result['query']!r}"
    )
    print("  PASS: response echoes the original raw query, not the expanded one")


if __name__ == "__main__":
    verify_abbreviation_query_finds_real_cs_club()
    verify_category_filter_still_applies()
    verify_query_field_is_the_original_raw_query()
    print("\nPASS: AI search verified")
