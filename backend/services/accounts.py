"""Sign-up and login: validation + orchestration on top of db.py + auth.py.

db.py stays pure CRUD; this module is where "is this a valid email",
"is this email already taken", and "does this password match" live.
"""

from __future__ import annotations

import re
import sqlite3

from backend import db
from backend.services.auth import create_access_token, hash_password, verify_password

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


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
