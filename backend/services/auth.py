"""Password hashing and login tokens for user accounts.

Password hashing uses the stdlib (hashlib.pbkdf2_hmac + secrets), not
bcrypt/passlib - deliberately, to avoid a compiled-extension dependency
on top of everything else in requirements.txt. PBKDF2-SHA256 at 260,000
iterations is OWASP's own 2023-recommended minimum for this algorithm and
is adequate for a student-club app's threat model. The stored hash is
self-describing ("pbkdf2_sha256$<iterations>$<salt>$<hash>") so the
iteration count (or algorithm) can change later without a migration -
verify_password() reads the iteration count back out of the stored value
instead of assuming ITERATIONS is still current.

Login tokens are stateless JWTs (PyJWT) carried by the frontend as
Authorization: Bearer <token> - no server-side session table, matching
this project's general preference for small, simple pieces over more
infrastructure than the problem needs.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import Header, HTTPException

load_dotenv()

JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "")
JWT_ALGORITHM = "HS256"
TOKEN_TTL = timedelta(days=30)

ITERATIONS = 260_000
_ALGO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS)
    return f"{_ALGO}${ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """True iff password matches password_hash. Never raises - a malformed
    stored hash (shouldn't happen, but this is a login path) just fails
    the check rather than 500ing."""
    try:
        algo, iterations_str, salt, expected_hex = password_hash.split("$")
        if algo != _ALGO:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), int(iterations_str)
        )
        return hmac.compare_digest(digest.hex(), expected_hex)
    except (ValueError, AttributeError):
        return False


def create_access_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.now(timezone.utc) + TOKEN_TTL,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Returns {"user_id": int, "email": str} or None if the token is
    missing, malformed, expired, or signed with a different secret."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return {"user_id": int(payload["sub"]), "email": payload["email"]}
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: require a valid "Authorization: Bearer <token>"
    header. Raises 401 if it's missing, malformed, expired, or the user it
    names no longer exists (deleted account). Import lives here (not in
    db.py) to avoid a circular import between auth.py and db.py."""
    from backend import db

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not logged in.")

    token = authorization.removeprefix("Bearer ").strip()
    decoded = decode_access_token(token)
    if decoded is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")

    user = db.get_user_by_id(decoded["user_id"])
    if user is None:
        raise HTTPException(status_code=401, detail="Account no longer exists.")

    return {"id": user["id"], "name": user["name"], "email": user["email"]}


if __name__ == "__main__":
    pw_hash = hash_password("correct horse battery staple")
    print("hash:", pw_hash)
    print("verify correct:", verify_password("correct horse battery staple", pw_hash))
    print("verify wrong:", verify_password("wrong password", pw_hash))

    token = create_access_token(42, "student@cornell.edu")
    print("token:", token)
    print("decoded:", decode_access_token(token))
    print("decoded garbage:", decode_access_token("not.a.token"))
