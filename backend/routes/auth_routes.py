"""POST /auth/register, POST /auth/login, GET /auth/me.

Thin routes over services/accounts.py - all validation/hashing/token logic
lives there and in services/auth.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.services import accounts
from backend.services.auth import get_current_user

router = APIRouter(prefix="/auth")


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(req: RegisterRequest):
    try:
        return accounts.register_user(req.name, req.email, req.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
def login(req: LoginRequest):
    try:
        return accounts.login_user(req.email, req.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}
