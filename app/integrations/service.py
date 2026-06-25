"""Google connection business logic: connect, callback, status, token refresh.

Each ensight owner connects their own Google account once. We store the refresh
token and mint fresh access tokens on demand, so the agent can act on their
calendar later without the owner being present.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import jwt
from fastapi import HTTPException, status

from app.core.config import settings
from app.integrations import google_oauth
from app.integrations.repository import GoogleConnectionRepository
from app.integrations.schemas import GoogleConnectionStatus

_STATE_TYPE = "google_oauth_state"
_STATE_TTL_MINUTES = 10
_ALGORITHM = "HS256"
# Refresh the access token slightly before it actually expires.
_EXPIRY_SKEW_SECONDS = 60


class IntegrationError(Exception):
    """Raised when the OAuth handshake fails (bad code/state)."""


class GoogleIntegrationService:
    def __init__(self, repository: GoogleConnectionRepository) -> None:
        self.repository = repository

    # --- connect / callback ----------------------------------------------
    def get_authorize_url(self, user_id: str) -> str:
        now = datetime.now(timezone.utc)
        state = jwt.encode(
            {
                "type": _STATE_TYPE,
                "user_id": user_id,
                "iat": now,
                "exp": now + timedelta(minutes=_STATE_TTL_MINUTES),
            },
            settings.session_secret,
            algorithm=_ALGORITHM,
        )
        return google_oauth.build_authorize_url(state)

    def handle_callback(self, code: str, state: str) -> str:
        """Validate ``state``, exchange ``code``, store the connection.

        Returns the owner's ``user_id`` so the caller can redirect them back.
        """
        try:
            payload = jwt.decode(
                state, settings.session_secret, algorithms=[_ALGORITHM]
            )
            if payload.get("type") != _STATE_TYPE:
                raise IntegrationError("Invalid state")
            user_id = payload["user_id"]
        except (jwt.PyJWTError, KeyError) as exc:
            raise IntegrationError("Invalid or expired state") from exc

        try:
            tokens = google_oauth.exchange_code(code)
        except httpx.HTTPError as exc:
            raise IntegrationError("Failed to exchange code with Google") from exc

        refresh_token = tokens.get("refresh_token")
        access_token = tokens.get("access_token")
        if not access_token or not refresh_token:
            # No refresh token usually means the user previously consented;
            # prompt=consent should prevent this, but guard anyway.
            raise IntegrationError(
                "Google did not return a refresh token. Disconnect and try again."
            )

        email = google_oauth.fetch_email(access_token)
        tz = google_oauth.fetch_calendar_timezone(access_token)

        self.repository.upsert(
            {
                "user_id": user_id,
                "google_email": email,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_expiry": self._expiry_from(tokens).isoformat(),
                "scope": tokens.get("scope"),
                "calendar_timezone": tz,
            }
        )
        return user_id

    # --- status / disconnect ----------------------------------------------
    def get_status(self, user_id: str) -> GoogleConnectionStatus:
        row = self.repository.get(user_id)
        if not row:
            return GoogleConnectionStatus(connected=False)
        return GoogleConnectionStatus(
            connected=True,
            email=row.get("google_email"),
            calendar_timezone=row.get("calendar_timezone"),
        )

    def disconnect(self, user_id: str) -> None:
        self.repository.delete(user_id)

    # --- token access (used by the booking service) -----------------------
    def get_connection(self, user_id: str) -> dict:
        row = self.repository.get(user_id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This business hasn't connected a Google Calendar.",
            )
        return row

    def get_valid_access_token(self, user_id: str) -> str:
        """Return a non-expired access token, refreshing if necessary."""
        row = self.get_connection(user_id)
        expiry = datetime.fromisoformat(row["token_expiry"])
        now = datetime.now(timezone.utc)
        if now < expiry - timedelta(seconds=_EXPIRY_SKEW_SECONDS):
            return row["access_token"]

        # Expired (or about to) — refresh and persist.
        try:
            tokens = google_oauth.refresh_access_token(row["refresh_token"])
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not refresh Google access. Reconnect the calendar.",
            ) from exc

        access_token = tokens["access_token"]
        self.repository.update(
            user_id,
            {
                "access_token": access_token,
                "token_expiry": self._expiry_from(tokens).isoformat(),
            },
        )
        return access_token

    def get_timezone(self, user_id: str) -> str:
        row = self.get_connection(user_id)
        return row.get("calendar_timezone") or "UTC"

    @staticmethod
    def _expiry_from(tokens: dict) -> datetime:
        expires_in = int(tokens.get("expires_in", 3600))
        return datetime.now(timezone.utc) + timedelta(seconds=expires_in)
