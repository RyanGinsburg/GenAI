"""GET/POST /clubs/saved — a logged-in user's "My Clubs" list.

Every route here requires auth (get_current_user) - saving/viewing saved
clubs is the one thing in this app that's gated behind having an account,
per the explicit product decision to let chatting/browsing stay anonymous.

Remove is POST (not DELETE /clubs/saved/{url}) specifically to avoid
URL-encoding a full website URL inside a path segment.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.services import saved_clubs
from backend.services.auth import get_current_user

router = APIRouter(prefix="/clubs/saved")


class SavedClubRequest(BaseModel):
    website_url: str


@router.get("")
def list_saved(current_user: dict = Depends(get_current_user)):
    return {"clubs": saved_clubs.get_saved_clubs_with_details(current_user["id"])}


@router.post("")
def save(req: SavedClubRequest, current_user: dict = Depends(get_current_user)):
    saved_clubs.save_club(current_user["id"], req.website_url)
    return {"clubs": saved_clubs.get_saved_clubs_with_details(current_user["id"])}


@router.post("/remove")
def unsave(req: SavedClubRequest, current_user: dict = Depends(get_current_user)):
    saved_clubs.unsave_club(current_user["id"], req.website_url)
    return {"clubs": saved_clubs.get_saved_clubs_with_details(current_user["id"])}
