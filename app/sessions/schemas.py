"""Models for agent sessions (the widget-facing auth flow)."""

from pydantic import BaseModel

from app.agents.schemas import Capability


class SessionRequest(BaseModel):
    # The agent's public key (pk_...), embedded in the website widget.
    public_key: str
    # Optional stable visitor id (e.g. from the widget's localStorage) so the
    # same browser counts as one unique visitor across sessions.
    visitor_id: str | None = None


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    agent_id: str
    capability: Capability
    visitor_id: str
    conversation_id: str


class AgentSession(BaseModel):
    """Decoded session context, attached to chat/voice requests."""

    user_id: str
    agent_id: str
    capability: Capability
    visitor_id: str
    conversation_id: str


class EndSessionResponse(BaseModel):
    conversation_id: str
    status: str = "processing"
