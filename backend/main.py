"""FastAPI app wiring together matching, resume parsing, research, accounts,
and the conversational profile-builder. Routes live in backend/routes/ (one
module per concern); this file just creates the app, initializes the local
SQLite db, and includes the routers.

- /auth/* — sign up / log in / who-am-i. Stateless JWT in
  Authorization: Bearer <token>. See services/auth.py, services/accounts.py.
- /chat/* — the conversational profile-builder (replaces the old one-shot
  POST /chat). See services/chat_profile.py.
- /matching/from-profile, /matching/refine — turns a built profile into
  diversified, grouped club matches, and re-searches from a conversational
  follow-up. See services/matching.py's match_clubs_diversified /
  services/categorize.py.
- /clubs — browse/search/filter the full club directory, no auth needed.
- /clubs/saved — a logged-in user's saved clubs (requires auth).
- /chats/saved — a logged-in user's saved chat/match-result snapshots
  (requires auth). See services/saved_chats.py.
- /research — per-club deadline/meeting/coffee-chat lookup, called only
  when explicitly requested (never automatic from any of the above).

No club ever gets researched, and nothing ever gets saved to an account,
without an explicit user action - matching CLAUDE.md's hard constraints.

Run it:
    uvicorn backend.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import db
from backend.routes import (
    auth_routes,
    browse_routes,
    chat_routes,
    matching_routes,
    research_routes,
    saved_chats_routes,
    saved_clubs_routes,
)

db.init_db()

app = FastAPI(title="Cornell Club Matching Agent")

# Dev-only: the frontend runs on a different origin than this API
# (localhost:3000 vs. uvicorn's 8000). Fine for local dev; tighten the
# allowed origins before any real deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router)
app.include_router(research_routes.router)
app.include_router(saved_clubs_routes.router)
app.include_router(saved_chats_routes.router)
app.include_router(browse_routes.router)
app.include_router(chat_routes.router)
app.include_router(matching_routes.router)
