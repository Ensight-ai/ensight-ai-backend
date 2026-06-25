"""Conversation browsing business logic (owner-gated)."""

from fastapi import HTTPException, status

from app.agents.service import AgentService
from app.conversations.message_repository import MessageRepository
from app.conversations.repository import ConversationRepository
from app.conversations.schemas import (
    ConversationDetail,
    ConversationSummary,
    Message,
)
from app.core.pagination import Page, PageParams


class ConversationService:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        agent_service: AgentService,
    ) -> None:
        self.conversations = conversations
        self.messages = messages
        self.agent_service = agent_service

    def list_conversations(
        self, agent_id: str, user_id: str, params: PageParams
    ) -> Page[ConversationSummary]:
        self.agent_service.ensure_owned(agent_id, user_id)

        conversations, total = self.conversations.page_by_agent(
            agent_id, params.limit, params.offset
        )
        counts = self.messages.counts_for_conversations(
            [c["id"] for c in conversations]
        )

        items = [
            ConversationSummary(**c, message_count=counts.get(c["id"], 0))
            for c in conversations
        ]
        return Page(
            items=items,
            total=total,
            limit=params.limit,
            offset=params.offset,
        )

    def get_conversation(
        self, agent_id: str, conversation_id: str, user_id: str
    ) -> ConversationDetail:
        self.agent_service.ensure_owned(agent_id, user_id)

        conversation = self.conversations.get_owned(conversation_id, agent_id)
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )

        rows = self.messages.list_by_conversation(conversation_id)
        messages = [Message(**m) for m in rows]
        return ConversationDetail(
            **conversation, message_count=len(messages), messages=messages
        )
