"""POST /research — moved verbatim out of main.py when routes were split
into this package. Internals untouched; research_agent.py accuracy work
is out of scope for this pass."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.services import research_cache
from backend.services.research_agent import research_club

router = APIRouter()


class ResearchRequest(BaseModel):
    website_urls: list[str]


@router.post("/research")
def research(req: ResearchRequest):
    """Research a specific list of clubs the student asked about — never
    called automatically from the chat/browse flows.

    Cached (research_cache.py) so re-asking about the same club within its
    TTL doesn't re-fetch the site or re-call the Claude API. A failed
    lookup (fetch error, API error) is NOT cached, so a transient failure
    (e.g. a one-off timeout) gets retried on the next request instead of
    being stuck for the full cache TTL.

    research_club() already never raises (see its docstring), but this
    still guards each one individually so something more fundamental
    breaking (e.g. the headless browser process) can't fail the whole
    request for every other club in the list.
    """
    results = []
    for url in req.website_urls:
        cached = research_cache.get_cached(url)
        if cached is not None:
            results.append(cached)
            continue

        try:
            result = research_club(url)
        except Exception as e:
            result = {
                "website_url": url,
                "application_deadline": None,
                "next_meeting": None,
                "info_session": [],
                "coffee_chat_link": [],
                "not_found": True,
                "error": f"Unexpected error researching this club: {e}",
            }

        if "error" not in result:
            research_cache.set_cached(url, result)
        results.append(result)

    return {"results": results}
