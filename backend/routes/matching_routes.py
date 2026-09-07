"""POST /matching/from-profile — turns a chat-built profile into grouped
club matches. POST /matching/refine — turns a post-results follow-up
message into an updated profile and re-searches. No auth needed. Never
calls research_agent.py - that's always a separate, explicit POST
/research."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.categorize import group_clubs_by_category
from backend.services.chat_profile import refine_profile
from backend.services.matching import match_clubs_diversified
from backend.services.profile_schema import StudentProfile

router = APIRouter(prefix="/matching")


class MatchingRequest(BaseModel):
    profile: StudentProfile


class RefineRequest(BaseModel):
    profile: StudentProfile
    message: str


@router.post("/from-profile")
def from_profile(req: MatchingRequest):
    matches = match_clubs_diversified(req.profile.model_dump(), top_k_total=30)
    return {"groups": group_clubs_by_category(matches)}


@router.post("/refine")
def refine(req: RefineRequest):
    result = refine_profile(req.profile.model_dump(), req.message)
    if result.get("error"):
        return {**result, "groups": None}
    matches = match_clubs_diversified(result["profile"], top_k_total=30)
    return {
        "reply": result["reply"],
        "profile": result["profile"],
        "groups": group_clubs_by_category(matches),
    }
