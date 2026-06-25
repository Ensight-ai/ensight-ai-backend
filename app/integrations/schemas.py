"""Models for third-party integrations (currently Google Calendar)."""

from pydantic import BaseModel


class GoogleConnectionStatus(BaseModel):
    connected: bool
    email: str | None = None
    calendar_timezone: str | None = None


class AuthorizeUrl(BaseModel):
    """Returned to the dashboard so it can open Google's consent screen."""

    authorize_url: str
