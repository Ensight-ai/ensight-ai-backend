"""Providers wiring the sessions feature for dependency injection."""

from fastapi import Depends

from app.agents.dependencies import get_agent_repository
from app.agents.repository import AgentRepository
from app.conversations.dependencies import get_conversation_repository
from app.conversations.repository import ConversationRepository
from app.sessions.service import SessionService


def get_session_service(
    agents: AgentRepository = Depends(get_agent_repository),
    conversations: ConversationRepository = Depends(get_conversation_repository),
) -> SessionService:
    return SessionService(agents, conversations)
