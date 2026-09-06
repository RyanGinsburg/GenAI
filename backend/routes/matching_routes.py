"""POST /matching/from-profile — turns a chat-built profile into grouped
club matches. No auth needed. Never calls research_agent.py - that's
always a separate, explicit POST /research."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.categorize import group_clubs_by_category
from backend.services.matching import match_clubs_for_profile

router = APIRouter(prefix="/matching")


class Profile(BaseModel):
    interests: list[str] = []
    mode: str | None = None
    time_commitment: str | None = None
    notes: str | None = None


class MatchingRequest(BaseModel):
    profile: Profile


@router.post("/from-profile")
def from_profile(req: MatchingRequest):
    matches = match_clubs_for_profile(req.profile.model_dump(), top_k_total=30)
    return {"groups": group_clubs_by_category(matches)}
