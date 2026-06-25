"""Models for browsing conversations and their messages."""

from datetime import datetime

from pydantic import BaseModel


class Message(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


class ConversationSummary(BaseModel):
    id: str
    agent_id: str
    visitor_id: str
    channel: str
    language: str | None = None  # detected conversation language (ISO code)
    started_at: datetime
    last_message_at: datetime | None = None
    message_count: int


class ConversationDetail(ConversationSummary):
    messages: list[Message]
