"""Providers wiring the analytics feature for dependency injection."""

from fastapi import Depends

from app.agents.dependencies import get_agent_service
from app.agents.service import AgentService
from app.analytics.service import AnalyticsService
from app.conversations.dependencies import (
    get_conversation_repository,
    get_message_repository,
)
from app.conversations.message_repository import MessageRepository
from app.conversations.repository import ConversationRepository


def get_analytics_service(
    conversations: ConversationRepository = Depends(get_conversation_repository),
    messages: MessageRepository = Depends(get_message_repository),
    agent_service: AgentService = Depends(get_agent_service),
) -> AnalyticsService:
    return AnalyticsService(conversations, messages, agent_service)
