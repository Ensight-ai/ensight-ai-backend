"""Public agent keys and signed agent-session tokens.

Flow:

1. Each agent has a stable, non-secret ``public_key`` (``pk_...``) that the
   owner embeds in their website widget.
2. The widget POSTs that key to ``/sessions`` and gets back a short-lived,
   signed session token scoped to that agent (its ``user_id`` + ``agent_id``
   + ``capability``).
3. Chat / voice requests carry that token; we decode it to know which
   user + agent to scope the RAG conversation to.
"""

import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings

_ALGORITHM = "HS256"
_SESSION_TYPE = "agent_session"


def generate_public_key() -> str:
    """A non-secret, URL-safe key embedded in the website widget."""
    return "pk_" + secrets.token_urlsafe(24)


def generate_visitor_id() -> str:
    """An anonymous id for a widget visitor (when the widget didn't send one)."""
    return "vis_" + secrets.token_urlsafe(16)


def create_session_token(
    *,
    user_id: str,
    agent_id: str,
    capability: str,
    visitor_id: str,
    conversation_id: str,
) -> tuple[str, int]:
    """Sign a session token. Returns ``(token, expires_in_seconds)``."""
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(minutes=settings.session_token_ttl_minutes)
    payload = {
        "type": _SESSION_TYPE,
        "sub": agent_id,
        "user_id": user_id,
        "agent_id": agent_id,
        "capability": capability,
        "visitor_id": visitor_id,
        "conversation_id": conversation_id,
        "iat": now,
        "exp": now + expires_delta,
    }
    token = jwt.encode(payload, settings.session_secret, algorithm=_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def decode_session_token(token: str) -> dict:
    """Decode and validate a session token. Raises on invalid/expired.

    Raises :class:`jwt.PyJWTError` (or :class:`ValueError` for the wrong
    token type), which callers translate into a 401.
    """
    payload = jwt.decode(token, settings.session_secret, algorithms=[_ALGORITHM])
    if payload.get("type") != _SESSION_TYPE:
        raise ValueError("Not an agent session token")
    return payload
