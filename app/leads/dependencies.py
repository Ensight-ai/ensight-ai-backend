"""Providers wiring the leads feature for dependency injection."""

from fastapi import Depends
from supabase import Client

from app.agents.dependencies import get_agent_service
from app.agents.service import AgentService
from app.conversations.dependencies import (
    get_conversation_repository,
    get_message_repository,
)
from app.conversations.message_repository import MessageRepository
from app.conversations.repository import ConversationRepository
from app.dependencies import get_db
from app.leads.repository import LeadRepository
from app.leads.service import LeadService


def get_lead_repository(db: Client = Depends(get_db)) -> LeadRepository:
    return LeadRepository(db)


def get_lead_service(
    leads: LeadRepository = Depends(get_lead_repository),
    conversations: ConversationRepository = Depends(get_conversation_repository),
    messages: MessageRepository = Depends(get_message_repository),
    agent_service: AgentService = Depends(get_agent_service),
) -> LeadService:
    return LeadService(leads, conversations, messages, agent_service)
