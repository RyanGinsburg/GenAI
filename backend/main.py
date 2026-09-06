"""FastAPI app wiring matching.py, resume_parser.py, and research_agent.py
together. See BUILD_PROMPTS.md's Step 5 for the spec.

Two routes:
- POST /chat — takes a student's message (and optional resume PDF), returns
  matched clubs. Matching only: this never calls research_agent.py. Getting
  a specific club's deadlines/meetings/coffee chats is a separate, explicit
  action (POST /research) so nothing slow or Claude-API-costly happens just
  from browsing matches — the frontend (Step 6) should only call /research
  when the student clicks something like "get info" on a specific club.
- POST /research — takes a list of club website_urls the student actually
  asked about and researches each one via research_agent.py, cached
  (research_cache.py) so repeat lookups don't re-fetch/re-call the API.

No auth, no database — matches CLAUDE.md's MVP scope for this step.

Run it:
    uvicorn backend.main:app --reload
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.services import matching, research_cache
from backend.services.research_agent import research_club
from backend.services.resume_parser import parse_resume

app = FastAPI(title="Cornell Club Matching Agent")

# Dev-only: the frontend (Step 6) runs on a different origin than this API
# (localhost:3000 vs. uvicorn's 8000). Fine for local dev; tighten the
# allowed origins before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

RESUME_DIR = Path(__file__).resolve().parent.parent / "data" / "resumes"


class ResearchRequest(BaseModel):
    website_urls: list[str]


@app.post("/chat")
async def chat(message: str = Form(...), resume: UploadFile | None = None):
    """Match clubs to a student's message, optionally informed by a resume.

    Returns matched clubs with only name/category/description/website_url/
    score — no deadline/meeting/coffee-chat info. That only comes from a
    separate POST /research call the student triggers explicitly.
    """
    resume_profile = None
    query = message

    if resume is not None:
        RESUME_DIR.mkdir(parents=True, exist_ok=True)
        resume_path = RESUME_DIR / f"{uuid.uuid4().hex}_{resume.filename}"
        resume_path.write_bytes(await resume.read())

        resume_profile = parse_resume(str(resume_path))
        if "error" not in resume_profile:
            interests = resume_profile.get("suggested_club_interests") or []
            if interests:
                query = f"{message}\n\nStudent's background suggests interest in: {', '.join(interests)}"

    matches = matching.match_clubs(query, top_k=10)

    return {
        "matches": matches,
        "resume_profile": resume_profile,
    }


@app.post("/research")
def research(req: ResearchRequest):
    """Research a specific list of clubs the student asked about — never
    called automatically from /chat (see module docstring).

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
                "info_session": None,
                "coffee_chat_link": None,
                "not_found": True,
                "error": f"Unexpected error researching this club: {e}",
            }

        if "error" not in result:
            research_cache.set_cached(url, result)
        results.append(result)

    return {"results": results}
