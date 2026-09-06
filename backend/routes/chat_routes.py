"""POST /chat/message, POST /chat/resume — the conversational profile-builder
that replaced the old one-shot POST /chat. No auth needed (chatting is
anonymous). Stateless: the frontend resends the full conversation history
every turn (see services/chat_profile.py's docstring for why).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel

from backend.paths import RESUME_DIR
from backend.services.chat_profile import continue_profile_chat
from backend.services.resume_parser import parse_resume

router = APIRouter(prefix="/chat")


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatMessageRequest(BaseModel):
    history: list[ChatTurn]
    resume_profile: dict | None = None


@router.post("/message")
def message(req: ChatMessageRequest):
    history = [{"role": turn.role, "content": turn.content} for turn in req.history]
    return continue_profile_chat(history, resume_profile=req.resume_profile)


@router.post("/resume")
async def upload_resume(resume: UploadFile):
    """Parse a resume PDF at any point during the chat (not just turn one).
    The frontend keeps the returned resume_profile client-side and sends it
    back on every subsequent /chat/message call - this route itself is
    stateless, like the conversation."""
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    resume_path = RESUME_DIR / f"{uuid.uuid4().hex}_{resume.filename}"
    resume_path.write_bytes(await resume.read())

    return {"resume_profile": parse_resume(str(resume_path))}
