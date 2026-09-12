"""GET/POST /chats/saved — a logged-in user's saved chat/match-result
snapshots ("Saved Chats", shown inside "My Clubs" alongside saved clubs).

Every route here requires auth (get_current_user), same as
saved_clubs_routes.py. Remove is POST (not DELETE) for consistency with
that module's style, even though a saved chat's id (a small integer) is
safe to put in the path unlike a full website URL, so /{chat_id} is used
for the single-item GET.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.services import saved_chats
from backend.services.auth import get_current_user

router = APIRouter(prefix="/chats/saved")


class SaveChatRequest(BaseModel):
    profile: dict
    groups: dict
    label: str | None = None


class RemoveChatRequest(BaseModel):
    chat_id: int


@router.get("")
def list_chats(current_user: dict = Depends(get_current_user)):
    return {"chats": saved_chats.list_saved_chats(current_user["id"])}


@router.get("/{chat_id}")
def get_chat(chat_id: int, current_user: dict = Depends(get_current_user)):
    chat = saved_chats.get_saved_chat_detail(current_user["id"], chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Saved chat not found.")
    return chat


@router.post("")
def save(req: SaveChatRequest, current_user: dict = Depends(get_current_user)):
    saved_chats.save_chat(current_user["id"], req.profile, req.groups, req.label)
    return {"chats": saved_chats.list_saved_chats(current_user["id"])}


@router.post("/remove")
def remove(req: RemoveChatRequest, current_user: dict = Depends(get_current_user)):
    saved_chats.remove_saved_chat(current_user["id"], req.chat_id)
    return {"chats": saved_chats.list_saved_chats(current_user["id"])}
