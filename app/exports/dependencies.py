"""Providers wiring the exports feature for dependency injection."""

from fastapi import Depends

from app.agents.dependencies import get_agent_service
from app.agents.service import AgentService
from app.analytics.dependencies import get_analytics_service
from app.analytics.service import AnalyticsService
from app.conversations.dependencies import (
    get_conversation_repository,
    get_message_repository,
)
from app.conversations.message_repository import MessageRepository
from app.conversations.repository import ConversationRepository
from app.exports.service import ExportService


def get_export_service(
    conversations: ConversationRepository = Depends(get_conversation_repository),
    messages: MessageRepository = Depends(get_message_repository),
    analytics_service: AnalyticsService = Depends(get_analytics_service),
    agent_service: AgentService = Depends(get_agent_service),
) -> ExportService:
    return ExportService(conversations, messages, analytics_service, agent_service)
