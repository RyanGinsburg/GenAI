"""Google Calendar OAuth2 (web-server authorization-code flow) and event
creation.

Hard constraint (CLAUDE.md): nothing reaches the user's calendar without an
explicit confirmation step in the UI first. This module creates events it is
handed; it does not decide what to add. It also never fabricates a date/time
- parse_event_datetime() returns None (not a guess) for any field that
doesn't resolve to one single concrete date/time, e.g. a range, multiple
sessions in one field, or genuinely vague text.

Why a real authorization-code flow, not BUILD_PROMPTS.md's original
"installed app flow" wording: that wording predates this app's real
multi-user accounts. A single local token.json (one Google account for the
whole process) doesn't fit a multi-student web app - each student needs
their own Google Calendar connected. This uses the standard OAuth 2.0
web-server flow instead: the browser is redirected to Google's consent
screen, Google redirects back with an authorization code, the backend
exchanges that for an access_token + refresh_token and stores them per user
(db.google_calendar_tokens) so a connection only has to happen once per
account.

Why raw REST via `requests` instead of google-auth-oauthlib/
google-api-python-client: same reasoning as research_agent.py's Firecrawl
integration - two fewer dependencies for what are otherwise simple, stable,
well-documented REST endpoints (Google's OAuth token endpoint and the
Calendar v3 REST API), with full control over the small set of calls
actually needed here.

Architecture note - bridging stateless-JWT auth with a header-less browser
redirect: this app's login tokens travel as an `Authorization: Bearer`
header via fetch(), but starting Google's consent flow means a real browser
navigation (window.location.href = ...), which can't carry custom headers.
build_authorization_url() bridges this by embedding the user's identity in
Google's own `state` query parameter as a short-lived signed JWT (reusing
services/auth.py's JWT_SECRET_KEY, a distinct payload/TTL from a login
access token) - the frontend calls GET /calendar/connect via an
authenticated fetch() to get this URL, then does a plain, header-less
redirect to it. The public callback route decodes `state` to recover which
user this is for.
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import jwt
import requests
from dateutil import parser as dateutil_parser
from dotenv import load_dotenv

from backend import db
from backend.services.auth import JWT_ALGORITHM, JWT_SECRET_KEY

load_dotenv()

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://localhost:8000")
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:3000")
REDIRECT_URI = f"{BACKEND_BASE_URL}/calendar/oauth/callback"

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"

CALENDAR_TZ = ZoneInfo("America/New_York")  # Cornell/Ithaca - see module
# docstring's parse_event_datetime note: this is a fixed assumption, not
# parsed from each field's text (a "ET"/"EDT" suffix, when present, is
# already what this timezone means for this app's one audience).
STATE_TOKEN_TTL_MINUTES = 10
REQUEST_TIMEOUT_SECONDS = 15  # short REST calls (token exchange/refresh, one
# event insert) - no long-poll needed here, unlike research_agent.py's crawl

DEFAULT_EVENT_DURATION = timedelta(hours=1)  # none of the extracted fields
# (application_deadline/next_meeting/info_session) carry an end time - this
# is a stated assumption, not something scraped from a club's site.

_TIME_RE = re.compile(r"\b\d{1,2}(:\d{2})?\s*(am|pm)\b", re.IGNORECASE)
_WEEKDAY_RE = re.compile(
    r"\b(mon(day)?|tue(s|sday)?|wed(nesday)?|thu(rs|rsday)?|fri(day)?|sat(urday)?|sun(day)?)\b",
    re.IGNORECASE,
)
_MONTH_RE = re.compile(
    r"\b(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|aug(ust)?|"
    r"sep(t|tember)?|oct(ober)?|nov(ember)?|dec(ember)?)\b",
    re.IGNORECASE,
)
_RANGE_JOIN_RE = re.compile(r"\b(and|or)\b|[-–—]", re.IGNORECASE)


def _get_calendar_tokens_or_raise(user_id: int) -> dict:
    tokens = db.get_google_calendar_tokens(user_id)
    if tokens is None:
        raise ValueError("Google Calendar isn't connected.")
    return tokens


def build_authorization_url(user_id: int) -> str:
    """Returns the full Google consent-screen URL for user_id to visit
    (via a plain browser redirect, not fetch()). Raises ValueError if
    Google OAuth isn't configured on this server."""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise ValueError("Google Calendar isn't configured on this server.")

    state = jwt.encode(
        {
            "purpose": "calendar_oauth",
            "user_id": user_id,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=STATE_TOKEN_TTL_MINUTES),
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": CALENDAR_SCOPE,
        # access_type=offline is required to get a refresh_token at all;
        # prompt=consent forces the consent screen (and a fresh
        # refresh_token) even on a reconnect - without it, Google only
        # issues a refresh_token on a user's first-ever grant for this
        # client+scope, which would silently break reconnecting after a
        # revoke in the user's own Google account settings.
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"


def verify_state_token(state: str) -> int:
    """Decodes/validates the state token from build_authorization_url().
    Returns user_id. Raises ValueError (one generic message - this is a
    public callback URL, no need to distinguish expired vs. malformed vs.
    wrong-purpose to the caller) on anything wrong."""
    try:
        payload = jwt.decode(state, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        if payload.get("purpose") != "calendar_oauth":
            raise ValueError
        return int(payload["user_id"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise ValueError("Invalid or expired calendar connection request. Please try connecting again.")


def _exchange_code_for_tokens(code: str) -> dict:
    """POST to Google's token endpoint for the authorization_code grant.
    Returns {"access_token", "refresh_token", "expires_in"}. Raises
    ValueError on any failure - never raises a raw requests/JSON error."""
    try:
        resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise ValueError(f"Network error contacting Google: {e}")

    if not resp.ok:
        raise ValueError(f"Google rejected the authorization code ({resp.status_code}).")

    try:
        data = resp.json()
    except ValueError:
        raise ValueError("Google returned an unexpected response.")

    if not data.get("refresh_token"):
        # Shouldn't happen with access_type=offline + prompt=consent, but
        # a token with no refresh_token is useless for this app's
        # connect-once design - fail loudly rather than silently store a
        # connection that will stop working the moment the access token
        # expires.
        raise ValueError("Google did not grant offline access. Please try connecting again.")

    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_in": data.get("expires_in", 3600),
    }


def _refresh_access_token(refresh_token: str) -> dict:
    """POST to Google's token endpoint for the refresh_token grant.
    Returns {"access_token", "expires_in", "refresh_token": str | None} -
    Google often omits refresh_token on a refresh response (the existing
    one is still valid); None here means "nothing new," never a guess.
    Raises ValueError on failure, with a distinct message when the refresh
    token itself has been revoked."""
    try:
        resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise ValueError(f"Network error contacting Google: {e}")

    try:
        data = resp.json()
    except ValueError:
        data = {}

    if not resp.ok:
        if data.get("error") == "invalid_grant":
            raise ValueError("Google Calendar access was revoked. Please reconnect.")
        raise ValueError(f"Google rejected the token refresh ({resp.status_code}).")

    if "access_token" not in data:
        raise ValueError("Google returned an unexpected response.")

    return {
        "access_token": data["access_token"],
        "expires_in": data.get("expires_in", 3600),
        "refresh_token": data.get("refresh_token"),
    }


def get_valid_access_token(user_id: int) -> str:
    """The one function other code should call to get a usable access
    token for user_id - refreshes it first if needed. Raises ValueError
    ("Google Calendar isn't connected.") if the user has never connected,
    or with Google's own reason if a refresh fails (e.g. revoked access)."""
    tokens = _get_calendar_tokens_or_raise(user_id)

    expires_at = datetime.fromisoformat(tokens["expires_at"])
    if expires_at > datetime.now(timezone.utc) + timedelta(seconds=60):
        return tokens["access_token"]

    refreshed = _refresh_access_token(tokens["refresh_token"])
    new_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=refreshed["expires_in"])
    ).isoformat()
    db.upsert_google_calendar_tokens(
        user_id,
        refreshed["access_token"],
        refreshed["refresh_token"] or tokens["refresh_token"],
        new_expires_at,
    )
    return refreshed["access_token"]


def connect_calendar(user_id: int, code: str) -> None:
    """Orchestrates the first-time connect: exchanges code for tokens and
    stores them. Raises ValueError on any failure (see
    _exchange_code_for_tokens)."""
    tokens = _exchange_code_for_tokens(code)
    expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
    ).isoformat()
    db.upsert_google_calendar_tokens(
        user_id, tokens["access_token"], tokens["refresh_token"], expires_at
    )


def has_explicit_time(text: str) -> bool:
    """True iff text contains something that looks like a clock time
    (e.g. "5:00 PM", "11:59PM"). Used to decide between a timed event and
    an all-day event for a field that did parse to a concrete date."""
    return bool(_TIME_RE.search(text))


def parse_event_datetime(text: str, *, now: datetime | None = None) -> datetime | None:
    """Best-effort parse of a club-site-extracted free-text field (e.g.
    "Thu, Sep 3, 11:59PM ET") into one concrete, timezone-aware datetime
    (America/New_York). Returns None - never a guess - when the text:
      - names more than one date/session (e.g. "Aug 27 ... and Aug 31 ...")
      - has no weekday/month token at all (nothing date-like to anchor on)
      - is otherwise unparseable (vague text like "sometime in the fall",
        or something dateutil's parser rejects outright)

    dateutil.parser.parse(..., fuzzy=True) does NOT raise on a multi-date
    string - it silently picks one and ignores the rest, which would be a
    fabrication (presenting one of several real sessions as if it were the
    only one). The weekday/month count check below exists specifically to
    catch that case before a parse is even attempted.

    No year stated in the text -> assumes the current year (from `now`,
    which defaults to datetime.now() - overridable for testing). This is a
    plain, stated assumption, not a "roll forward to next year if that
    would be in the past" guess.
    """
    now = now or datetime.now()

    weekday_hits = len(_WEEKDAY_RE.findall(text))
    month_hits = len(_MONTH_RE.findall(text))
    if weekday_hits == 0 and month_hits == 0:
        return None
    if (weekday_hits + month_hits) > 1 and _RANGE_JOIN_RE.search(text):
        # More than one date-like token AND a joining word/dash between
        # them (e.g. "Mon ... and Fri ...", "Sep 3 - Sep 5") - a range or
        # multiple sessions, not one concrete date.
        return None

    default = datetime(now.year, 1, 1)
    try:
        # ignoretz=True: a stray "ET"/"EST"/"EDT" in the source text would
        # otherwise make dateutil warn that it doesn't recognize the
        # abbreviation - harmless since CALENDAR_TZ is applied unconditionally
        # right after anyway (this app has exactly one timezone, Cornell's).
        parsed = dateutil_parser.parse(text, default=default, fuzzy=True, ignoretz=True)
    except (dateutil_parser.ParserError, ValueError, OverflowError):
        return None

    return parsed.replace(tzinfo=CALENDAR_TZ)


def create_calendar_event(
    access_token: str,
    summary: str,
    description: str,
    start_dt: datetime | None = None,
    *,
    all_day_date: date | None = None,
) -> dict:
    """Creates one event on the user's primary Google Calendar. Exactly
    one of start_dt (a timed event, DEFAULT_EVENT_DURATION long - no
    extracted field carries its own end time) or all_day_date (a
    date-only event, using Google's exclusive-end-date-plus-one-day
    convention) should be given. Returns the created event's JSON
    ("id", "htmlLink", ...). Raises ValueError with Google's own rejection
    reason on any failure. Does NOT special-case a 401/expired token -
    callers must get a valid token via get_valid_access_token() first."""
    if start_dt is not None:
        end_dt = start_dt + DEFAULT_EVENT_DURATION
        body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": str(CALENDAR_TZ)},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": str(CALENDAR_TZ)},
        }
    elif all_day_date is not None:
        body = {
            "summary": summary,
            "description": description,
            "start": {"date": all_day_date.isoformat()},
            "end": {"date": (all_day_date + timedelta(days=1)).isoformat()},
        }
    else:
        raise ValueError("create_calendar_event needs either start_dt or all_day_date.")

    try:
        resp = requests.post(
            GOOGLE_CALENDAR_EVENTS_URL,
            json=body,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise ValueError(f"Network error creating the calendar event: {e}")

    if not resp.ok:
        raise ValueError(f"Google Calendar rejected the event ({resp.status_code}): {resp.text[:200]}")

    try:
        return resp.json()
    except ValueError:
        raise ValueError("Google Calendar returned an unexpected response.")


if __name__ == "__main__":
    print("--- parse_event_datetime self-test ---")

    fixed_now = datetime(2026, 9, 12)

    cases = [
        ("Thu, Sep 3, 11:59PM ET", True),
        ("Thu, Aug 27 @ 5:00 PM and Mon, Aug 31 @ 5:00 PM, Location: Gates G01", False),
        ("sometime in the fall", False),
        ("September 3, 2026", True),
    ]
    for text, should_parse in cases:
        result = parse_event_datetime(text, now=fixed_now)
        status = "parsed" if result is not None else "None"
        ok = "PASS" if (result is not None) == should_parse else "FAIL"
        print(f"{ok}: {text!r} -> {status} ({result})")

    date_only = parse_event_datetime("September 3, 2026", now=fixed_now)
    print(
        "PASS" if not has_explicit_time("September 3, 2026") else "FAIL",
        ": has_explicit_time('September 3, 2026') ->",
        has_explicit_time("September 3, 2026"),
    )
    print(
        "PASS" if has_explicit_time("Thu, Sep 3, 11:59PM ET") else "FAIL",
        ": has_explicit_time('Thu, Sep 3, 11:59PM ET') ->",
        has_explicit_time("Thu, Sep 3, 11:59PM ET"),
    )
