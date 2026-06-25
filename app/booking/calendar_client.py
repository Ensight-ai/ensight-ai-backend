"""Google Calendar REST calls used for booking (httpx, no extra deps).

Two operations: query free/busy on the owner's primary calendar, and create an
event with a Google Meet link inviting the visitor. The caller supplies a valid
access token (the integrations service handles refresh).
"""

from __future__ import annotations

import secrets
from datetime import datetime

import httpx

_FREEBUSY_ENDPOINT = "https://www.googleapis.com/calendar/v3/freeBusy"
_EVENTS_ENDPOINT = (
    "https://www.googleapis.com/calendar/v3/calendars/primary/events"
)
_TIMEOUT = httpx.Timeout(20.0)


def _auth(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def free_busy(
    access_token: str, time_min: datetime, time_max: datetime
) -> list[tuple[datetime, datetime]]:
    """Return busy intervals on the primary calendar within the window.

    ``time_min``/``time_max`` must be timezone-aware. Returned datetimes are
    timezone-aware (as Google reports them, typically UTC).
    """
    resp = httpx.post(
        _FREEBUSY_ENDPOINT,
        headers=_auth(access_token),
        json={
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "items": [{"id": "primary"}],
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    calendars = resp.json().get("calendars", {})
    busy = calendars.get("primary", {}).get("busy", [])
    intervals: list[tuple[datetime, datetime]] = []
    for b in busy:
        intervals.append(
            (
                datetime.fromisoformat(b["start"]),
                datetime.fromisoformat(b["end"]),
            )
        )
    return intervals


def create_event(
    access_token: str,
    *,
    summary: str,
    description: str,
    start: datetime,
    end: datetime,
    timezone: str,
    attendee_emails: list[str],
) -> dict:
    """Create an event with a Meet link and invite attendees.

    Returns ``{"event_id", "meet_link", "html_link"}``. ``sendUpdates=all``
    emails the invite (with the Meet link) to the attendees.
    """
    body = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start.isoformat(), "timeZone": timezone},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone},
        "attendees": [{"email": e} for e in attendee_emails if e],
        "conferenceData": {
            "createRequest": {
                "requestId": secrets.token_hex(16),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    resp = httpx.post(
        _EVENTS_ENDPOINT,
        headers=_auth(access_token),
        params={"conferenceDataVersion": 1, "sendUpdates": "all"},
        json=body,
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        "event_id": data.get("id"),
        "meet_link": data.get("hangoutLink"),
        "html_link": data.get("htmlLink"),
    }
