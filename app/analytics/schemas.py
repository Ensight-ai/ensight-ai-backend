"""Models for agent analytics."""

from datetime import datetime

from pydantic import BaseModel


class DailyCount(BaseModel):
    date: str  # YYYY-MM-DD
    conversations: int
    messages: int


class AgentAnalytics(BaseModel):
    agent_id: str
    unique_visitors: int
    total_conversations: int  # number of uses
    total_messages: int
    questions_asked: int  # visitor (user) messages
    answers_given: int  # assistant messages
    avg_messages_per_conversation: float
    first_activity: datetime | None = None
    last_activity: datetime | None = None
    # Per-day counts for the last 30 days.
    daily: list[DailyCount]
    # Most recent questions visitors asked.
    recent_questions: list[str]
