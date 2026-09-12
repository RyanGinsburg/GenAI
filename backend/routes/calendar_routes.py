"""GET /calendar/status, GET /calendar/connect, GET /calendar/oauth/callback,
POST /calendar/add-events — Google Calendar OAuth connect flow and event
creation.

status/connect/add-events all require auth (get_current_user), same as
saved_clubs_routes.py. oauth/callback is the one public route here - it's
Google's own browser redirect landing back on this server, which can't
carry an Authorization header; see services/calendar_sync.py's module
docstring for how the `state` parameter substitutes for that.

Per CLAUDE.md's hard constraint, POST /calendar/add-events is the only
route that ever touches the user's actual calendar, and it's only ever
called from the frontend's explicit "Add to Google Calendar" confirmation
step - nothing here runs automatically.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from backend import db
from backend.services import calendar_sync
from backend.services.auth import get_current_user

router = APIRouter(prefix="/calendar")


class CalendarEventRequest(BaseModel):
    website_url: str
    club_name: str
    field_key: str
    field_label: str
    raw_text: str


class AddEventsRequest(BaseModel):
    events: list[CalendarEventRequest]


@router.get("/status")
def status(current_user: dict = Depends(get_current_user)):
    connected = db.get_google_calendar_tokens(current_user["id"]) is not None
    return {"connected": connected}


@router.get("/connect")
def connect(current_user: dict = Depends(get_current_user)):
    """Called via an authenticated fetch() - returns the URL to redirect
    the browser to next. Doesn't redirect itself, since the caller still
    needs the JWT-authenticated response to know it's really talking to
    this backend before handing off to a plain browser navigation."""
    try:
        return {"authorization_url": calendar_sync.build_authorization_url(current_user["id"])}
    except ValueError as e:
        # Missing GOOGLE_CLIENT_ID/SECRET is a server misconfiguration, not
        # something the user did wrong - 500, unlike the 400s below.
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/oauth/callback")
def oauth_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    """Google's own redirect target - no auth dependency here (a plain
    browser GET can't carry an Authorization header). Always redirects
    back to the frontend rather than returning JSON or raising, since
    nothing calls this route via fetch() - it's only ever a real browser
    navigation Google performs. Never surfaces the internal error reason
    in the (public) redirect URL."""
    if error or not code or not state:
        return RedirectResponse(f"{calendar_sync.FRONTEND_BASE_URL}/?calendarConnected=false")

    try:
        user_id = calendar_sync.verify_state_token(state)
        calendar_sync.connect_calendar(user_id, code)
    except ValueError:
        return RedirectResponse(f"{calendar_sync.FRONTEND_BASE_URL}/?calendarConnected=false")

    return RedirectResponse(f"{calendar_sync.FRONTEND_BASE_URL}/?calendarConnected=true")


@router.post("/add-events")
def add_events(req: AddEventsRequest, current_user: dict = Depends(get_current_user)):
    """Creates one calendar event per confirmed field. Fails the whole
    request with a 409 up front if Calendar isn't connected (or the
    connection is no longer valid) - one clean signal instead of an
    identical per-event failure for every item in the batch. Every
    requested event that gets past that point gets its own result entry
    (added / skipped_unparseable / failed) - nothing is silently dropped.
    """
    try:
        access_token = calendar_sync.get_valid_access_token(current_user["id"])
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    results = []
    for event in req.events:
        parsed = calendar_sync.parse_event_datetime(event.raw_text)
        if parsed is None:
            results.append(
                {
                    "website_url": event.website_url,
                    "field_key": event.field_key,
                    "status": "skipped_unparseable",
                    "message": (
                        f"Couldn't determine a single concrete date/time for "
                        f"\"{event.field_label}\" from the text on {event.club_name}'s "
                        "site - please check it and add manually if needed."
                    ),
                }
            )
            continue

        summary = f"{event.club_name}: {event.field_label}"
        description = (
            f"{event.field_label} for {event.club_name}\n"
            f"Source: {event.website_url}\n"
            f"Original text: {event.raw_text}"
        )

        try:
            if calendar_sync.has_explicit_time(event.raw_text):
                created = calendar_sync.create_calendar_event(
                    access_token, summary, description, parsed
                )
            else:
                created = calendar_sync.create_calendar_event(
                    access_token, summary, description, all_day_date=parsed.date()
                )
        except ValueError as e:
            results.append(
                {
                    "website_url": event.website_url,
                    "field_key": event.field_key,
                    "status": "failed",
                    "message": str(e),
                }
            )
            continue

        results.append(
            {
                "website_url": event.website_url,
                "field_key": event.field_key,
                "status": "added",
                "message": f"Added \"{event.field_label}\" to your calendar.",
                "event_link": created.get("htmlLink"),
            }
        )

    return {"results": results}
