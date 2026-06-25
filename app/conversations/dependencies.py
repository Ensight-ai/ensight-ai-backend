"""Providers wiring the conversations feature for dependency injection."""

from fastapi import Depends
from supabase import Client

from app.agents.dependencies import get_agent_service
from app.agents.service import AgentService
from app.conversations.message_repository import MessageRepository
from app.conversations.repository import ConversationRepository
from app.conversations.service import ConversationService
from app.dependencies import get_db


def get_conversation_repository(
    db: Client = Depends(get_db),
) -> ConversationRepository:
    return ConversationRepository(db)


def get_message_repository(db: Client = Depends(get_db)) -> MessageRepository:
    return MessageRepository(db)


def get_conversation_service(
    conversations: ConversationRepository = Depends(get_conversation_repository),
    messages: MessageRepository = Depends(get_message_repository),
    agent_service: AgentService = Depends(get_agent_service),
) -> ConversationService:
    return ConversationService(conversations, messages, agent_service)
