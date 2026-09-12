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


class GoogleAuthRequest(BaseModel):
    credential: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


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


@router.post("/google")
def google_sign_in(req: GoogleAuthRequest):
    try:
        return accounts.google_sign_in(req.credential)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    try:
        accounts.request_password_reset(req.email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    # Always the same response, whether or not the email matched an
    # account - see accounts.request_password_reset's non-enumeration note.
    return {"message": "If an account exists for that email, we've sent a password reset link."}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest):
    try:
        return accounts.reset_password(req.token, req.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}
