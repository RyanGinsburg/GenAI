"""Verifies a Google Identity Services ID token server-side.

Only needs GOOGLE_CLIENT_ID as the expected audience - unlike an
authorization-code OAuth flow, verifying an ID token the frontend already
obtained never touches GOOGLE_CLIENT_SECRET.
"""

from __future__ import annotations

import os

import google.auth.exceptions
from dotenv import load_dotenv
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

load_dotenv()

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")


def verify_google_id_token(credential: str) -> dict:
    """Returns {"google_id", "email", "name", "email_verified"}. Raises
    ValueError with a user-facing message if the token is missing,
    malformed, expired, or signed for a different client - matching this
    codebase's convention that services/*.py raises ValueError for
    user-facing failures, converted to HTTPException only in routes/*.py."""
    if not credential:
        raise ValueError("Invalid Google credential.")

    try:
        idinfo = id_token.verify_oauth2_token(
            credential, google_requests.Request(), GOOGLE_CLIENT_ID
        )
    except (ValueError, google.auth.exceptions.GoogleAuthError):
        raise ValueError("Invalid Google credential.")

    email = idinfo.get("email")
    if not email:
        raise ValueError("Invalid Google credential.")

    return {
        "google_id": idinfo["sub"],
        "email": email,
        "name": idinfo.get("name") or email.split("@")[0],
        "email_verified": bool(idinfo.get("email_verified", False)),
    }
