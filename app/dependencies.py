"""Shared FastAPI dependencies."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client

from app.agents.schemas import Capability
from app.core.security import decode_session_token
from app.core.supabase import get_supabase, get_supabase_admin
from app.sessions.schemas import AgentSession

# Expects an "Authorization: Bearer <access_token>" header.
bearer_scheme = HTTPBearer()


# --- injectable Supabase clients ------------------------------------------
def get_db() -> Client:
    """Service-role client used by repositories (bypasses RLS)."""
    return get_supabase_admin()


def get_auth_client() -> Client:
    """Anon client used for auth flows (signup / login)."""
    return get_supabase()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Validate the bearer token with Supabase and return the auth user.

    The returned object exposes ``.id`` (the user's UUID) and ``.email``,
    which downstream code uses as the ``user_id`` for agents and embeddings.
    """
    token = credentials.credentials
    try:
        response = get_supabase().auth.get_user(token)
    except Exception:
        response = None

    if response is None or response.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return response.user


def require_admin(current_user=Depends(get_current_user)):
    """Gate a route to the emails listed in ADMIN_EMAILS (founder dashboard)."""
    from app.core.config import settings

    admins = set(settings.admin_emails)  # already normalised to lowercase
    email = (getattr(current_user, "email", "") or "").lower()
    if not admins or email not in admins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admins only"
        )
    return current_user


def get_agent_session(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AgentSession:
    """Validate an agent session token and return its scope.

    Used by widget-facing chat/voice routes. The token is the one issued by
    ``POST /sessions`` in exchange for an agent's public key.
    """
    try:
        payload = decode_session_token(credentials.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AgentSession(
        user_id=payload["user_id"],
        agent_id=payload["agent_id"],
        capability=payload["capability"],
        visitor_id=payload["visitor_id"],
        conversation_id=payload["conversation_id"],
    )


def require_chat(session: AgentSession = Depends(get_agent_session)) -> AgentSession:
    """Gate a route to agents that can chat (capability chat or both)."""
    if session.capability not in (Capability.chat, Capability.both):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This agent does not support chat.",
        )
    return session


def require_voice(session: AgentSession = Depends(get_agent_session)) -> AgentSession:
    """Gate a route to agents that can talk (capability voice or both)."""
    if session.capability not in (Capability.voice, Capability.both):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This agent does not support voice.",
        )
    return session
