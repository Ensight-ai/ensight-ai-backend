"""Analytics business logic: derive insights from conversations + messages."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.agents.service import AgentService
from app.analytics.schemas import AgentAnalytics, DailyCount
from app.conversations.message_repository import MessageRepository
from app.conversations.repository import ConversationRepository

_DAILY_WINDOW = 30


def _day(ts: str | None) -> str:
    return ts[:10] if ts else ""


class AnalyticsService:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        agent_service: AgentService,
    ) -> None:
        self.conversations = conversations
        self.messages = messages
        self.agent_service = agent_service

    def get_analytics(self, agent_id: str, user_id: str) -> AgentAnalytics:
        """Owner-gated analytics for an agent."""
        self.agent_service.ensure_owned(agent_id, user_id)
        return self.compute(agent_id)

    def compute(self, agent_id: str) -> AgentAnalytics:
        conversations = self.conversations.list_by_agent(agent_id)
        messages = self.messages.list_by_agent(agent_id, "role,created_at")

        total_conversations = len(conversations)
        unique_visitors = len({c["visitor_id"] for c in conversations})
        questions_asked = sum(1 for m in messages if m["role"] == "user")
        answers_given = sum(1 for m in messages if m["role"] == "assistant")
        total_messages = len(messages)
        avg = (
            round(total_messages / total_conversations, 2)
            if total_conversations
            else 0.0
        )

        timestamps = (
            [c["started_at"] for c in conversations if c.get("started_at")]
            + [
                c["last_message_at"]
                for c in conversations
                if c.get("last_message_at")
            ]
            + [m["created_at"] for m in messages if m.get("created_at")]
        )
        first_activity = min(timestamps) if timestamps else None
        last_activity = max(timestamps) if timestamps else None

        convo_by_day: dict[str, int] = defaultdict(int)
        for c in conversations:
            convo_by_day[_day(c.get("started_at"))] += 1
        msg_by_day: dict[str, int] = defaultdict(int)
        for m in messages:
            msg_by_day[_day(m.get("created_at"))] += 1

        today = datetime.now(timezone.utc).date()
        daily = [
            DailyCount(
                date=(day := (today - timedelta(days=offset)).isoformat()),
                conversations=convo_by_day.get(day, 0),
                messages=msg_by_day.get(day, 0),
            )
            for offset in range(_DAILY_WINDOW - 1, -1, -1)
        ]

        return AgentAnalytics(
            agent_id=agent_id,
            unique_visitors=unique_visitors,
            total_conversations=total_conversations,
            total_messages=total_messages,
            questions_asked=questions_asked,
            answers_given=answers_given,
            avg_messages_per_conversation=avg,
            first_activity=first_activity,
            last_activity=last_activity,
            daily=daily,
            recent_questions=self.messages.recent_questions(agent_id, 10),
        )
