"""Providers wiring the chat feature for dependency injection.

The engines are imported lazily inside the provider functions so the heavy
RAG / speech stacks load only when /chat or /voice is actually called.
"""

from fastapi import Depends

from app.agents.dependencies import get_agent_repository
from app.agents.repository import AgentRepository
from app.booking.dependencies import get_booking_service
from app.booking.service import BookingService
from app.chat.service import ChatService
from app.chat.voice_service import VoiceService
from app.conversations.dependencies import (
    get_conversation_repository,
    get_message_repository,
)
from app.conversations.message_repository import MessageRepository
from app.conversations.repository import ConversationRepository


def get_rag_engine():
    from rag_bot.rag_engine import get_engine

    return get_engine()


def get_voice_engine():
    from rag_bot.voice_engine import get_voice_engine as _get_voice_engine

    return _get_voice_engine()


def get_chat_service(
    conversations: ConversationRepository = Depends(get_conversation_repository),
    messages: MessageRepository = Depends(get_message_repository),
    engine=Depends(get_rag_engine),
    agents: AgentRepository = Depends(get_agent_repository),
    booking_service: BookingService = Depends(get_booking_service),
) -> ChatService:
    return ChatService(conversations, messages, engine, agents, booking_service)


def get_voice_service(
    conversations: ConversationRepository = Depends(get_conversation_repository),
    messages: MessageRepository = Depends(get_message_repository),
    engine=Depends(get_voice_engine),
    rag_engine=Depends(get_rag_engine),
) -> VoiceService:
    return VoiceService(conversations, messages, engine, rag_engine)
