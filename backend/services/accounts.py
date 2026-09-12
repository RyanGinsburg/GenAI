"""Sign-up and login: validation + orchestration on top of db.py + auth.py.

db.py stays pure CRUD; this module is where "is this a valid email",
"is this email already taken", and "does this password match" live.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from backend import db
from backend.services import email_service, google_auth
from backend.services.auth import create_access_token, hash_password, verify_password

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8
RESET_TOKEN_TTL = timedelta(hours=1)

logger = logging.getLogger(__name__)


def _public_user(user_row: dict) -> dict:
    """Strip password_hash before a user record ever leaves this module."""
    return {"id": user_row["id"], "name": user_row["name"], "email": user_row["email"]}


def register_user(name: str, email: str, password: str) -> dict:
    """Returns {"token": str, "user": {...}}. Raises ValueError with a
    user-facing message on bad input or a duplicate email."""
    name = (name or "").strip()
    email = (email or "").strip().lower()

    if not name:
        raise ValueError("Name is required.")
    if not EMAIL_RE.match(email):
        raise ValueError("Please enter a valid email address.")
    if len(password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    try:
        user_id = db.create_user(name, email, hash_password(password))
    except sqlite3.IntegrityError:
        raise ValueError("An account with this email already exists.")

    token = create_access_token(user_id, email)
    return {"token": token, "user": {"id": user_id, "name": name, "email": email}}


def login_user(email: str, password: str) -> dict:
    """Returns {"token": str, "user": {...}}. Raises ValueError with a
    generic message on any failure (don't reveal whether the email exists)."""
    email = (email or "").strip().lower()
    user = db.get_user_by_email(email)
    if user is None or not verify_password(password or "", user["password_hash"]):
        raise ValueError("Incorrect email or password.")

    token = create_access_token(user["id"], user["email"])
    return {"token": token, "user": _public_user(user)}


def google_sign_in(id_token_str: str) -> dict:
    """Returns {"token": str, "user": {...}} - same shape as
    register_user/login_user, so the frontend can treat all three
    identically. Provisions an account on first use (no separate
    "register with Google" step): looks up by google_id first, then by
    email (auto-linking an existing password account, since Google has
    already verified that email address), then creates a brand new
    Google-only account. Raises ValueError with a user-facing message on
    any failure."""
    idinfo = google_auth.verify_google_id_token(id_token_str)
    if not idinfo["email_verified"]:
        raise ValueError("Your Google account's email is not verified.")

    email = idinfo["email"].strip().lower()
    google_id = idinfo["google_id"]

    user = db.get_user_by_google_id(google_id)
    if user is None:
        user = db.get_user_by_email(email)
        if user is not None:
            db.link_google_id_to_user(user["id"], google_id)
            user = db.get_user_by_id(user["id"])
        else:
            try:
                user_id = db.create_google_user(idinfo["name"], email, google_id)
            except sqlite3.IntegrityError:
                raise ValueError("An account with this email already exists.")
            user = db.get_user_by_id(user_id)

    token = create_access_token(user["id"], user["email"])
    return {"token": token, "user": _public_user(user)}


def request_password_reset(email: str) -> None:
    """Always succeeds (returns None) for a well-formed email, whether or
    not an account exists - same non-enumeration principle as
    login_user's generic "Incorrect email or password.". Raises ValueError
    only for a malformed email, never for "not found"."""
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError("Please enter a valid email address.")

    user = db.get_user_by_email(email)
    if user is None:
        return

    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + RESET_TOKEN_TTL).isoformat()
    db.create_password_reset_token(token, user["id"], expires_at)

    frontend_base_url = os.environ.get("FRONTEND_BASE_URL", "http://localhost:3000")
    reset_link = f"{frontend_base_url}/?resetToken={token}"
    try:
        email_service.send_password_reset_email(user["email"], reset_link)
    except Exception:
        # Don't let an SMTP failure leak through the response (that would
        # distinguish "exists but couldn't send" from "doesn't exist") -
        # but don't silently pretend it worked either; log it so a
        # misconfigured SMTP server is loudly visible to the developer.
        logger.exception("Failed to send password reset email to %s", user["email"])


def reset_password(token: str, new_password: str) -> dict:
    """Returns {"token": str, "user": {...}} - resetting logs the user in
    (same shape as register_user/login_user/google_sign_in). Raises
    ValueError with one generic message for a missing, already-used, or
    expired token (no distinction between the three, same non-enumeration
    instinct as elsewhere in this module). Overwrites password_hash
    unconditionally, so this also lets a Google-only account (sentinel
    password_hash) set its first real password."""
    if len(new_password or "") < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

    row = db.get_password_reset_token(token)
    now = datetime.now(timezone.utc).isoformat()
    if row is None or row["used_at"] is not None or row["expires_at"] < now:
        raise ValueError("This password reset link is invalid or has expired.")

    db.update_user_password(row["user_id"], hash_password(new_password))
    db.mark_password_reset_token_used(token)

    user = db.get_user_by_id(row["user_id"])
    access_token = create_access_token(user["id"], user["email"])
    return {"token": access_token, "user": _public_user(user)}


if __name__ == "__main__":
    import time

    test_email = f"test-{int(time.time())}@cornell.edu"
    result = register_user("Test Student", test_email, "testpassword123")
    print("registered:", result)

    login_result = login_user(test_email, "testpassword123")
    print("logged in:", login_result)

    try:
        register_user("Test Student 2", test_email, "anotherpassword")
    except ValueError as e:
        print("duplicate email correctly rejected:", e)

    try:
        login_user(test_email, "wrongpassword")
    except ValueError as e:
        print("wrong password correctly rejected:", e)
