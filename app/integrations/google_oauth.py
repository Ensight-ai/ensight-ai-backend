"""Thin Google OAuth 2.0 + userinfo client (REST via httpx, no extra deps).

Handles only the protocol bits: build the consent URL, exchange the code for
tokens, refresh an access token, and read the connected account's email and
calendar timezone. Persistence and policy live in the service layer.
"""

from urllib.parse import urlencode

import httpx

from app.core.config import settings

_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v2/userinfo"
_TIMEZONE_ENDPOINT = (
    "https://www.googleapis.com/calendar/v3/users/me/settings/timezone"
)

# Read availability (calendar.readonly covers free/busy) + create events with
# Meet links. openid/email let us record which Google account connected.
SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

_TIMEOUT = httpx.Timeout(15.0)


def build_authorize_url(state: str) -> str:
    """The Google consent URL to send the owner to.

    ``access_type=offline`` + ``prompt=consent`` ensure we receive a refresh
    token so we can act on the calendar later without the user present.
    """
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": settings.google_oauth_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{_AUTH_ENDPOINT}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """Trade an authorization code for access + refresh tokens."""
    resp = httpx.post(
        _TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(refresh_token: str) -> dict:
    """Get a fresh access token from a stored refresh token."""
    resp = httpx.post(
        _TOKEN_ENDPOINT,
        data={
            "refresh_token": refresh_token,
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "grant_type": "refresh_token",
        },
        timeout=_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_email(access_token: str) -> str | None:
    resp = httpx.get(
        _USERINFO_ENDPOINT,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=_TIMEOUT,
    )
    if resp.is_success:
        return resp.json().get("email")
    return None


def fetch_calendar_timezone(access_token: str) -> str | None:
    resp = httpx.get(
        _TIMEZONE_ENDPOINT,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=_TIMEOUT,
    )
    if resp.is_success:
        return resp.json().get("value")
    return None
