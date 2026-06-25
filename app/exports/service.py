"""Export business logic: build JSON / CSV downloads of an agent's data."""

import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timezone

from fastapi.responses import Response

from app.agents.service import AgentService
from app.analytics.service import AnalyticsService
from app.conversations.message_repository import MessageRepository
from app.conversations.repository import ConversationRepository


class ExportService:
    def __init__(
        self,
        conversations: ConversationRepository,
        messages: MessageRepository,
        analytics_service: AnalyticsService,
        agent_service: AgentService,
    ) -> None:
        self.conversations = conversations
        self.messages = messages
        self.analytics_service = analytics_service
        self.agent_service = agent_service

    def export_agent(self, agent_id: str, user_id: str, fmt: str) -> Response:
        """Export an agent's conversations + messages as JSON or CSV."""
        self.agent_service.ensure_owned(agent_id, user_id)

        conversations = self.conversations.list_by_agent(agent_id)
        messages = self.messages.list_by_agent(agent_id, "*")

        if fmt == "csv":
            return self._csv_response(agent_id, conversations, messages)
        return self._json_response(agent_id, conversations, messages)

    def _csv_response(
        self, agent_id: str, conversations: list[dict], messages: list[dict]
    ) -> Response:
        convo_by_id = {c["id"]: c for c in conversations}
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "conversation_id",
                "visitor_id",
                "channel",
                "role",
                "content",
                "created_at",
            ]
        )
        for m in messages:
            convo = convo_by_id.get(m["conversation_id"], {})
            writer.writerow(
                [
                    m["conversation_id"],
                    convo.get("visitor_id", ""),
                    convo.get("channel", ""),
                    m["role"],
                    m["content"],
                    m["created_at"],
                ]
            )
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="agent_{agent_id}_export.csv"'
                )
            },
        )

    def _json_response(
        self, agent_id: str, conversations: list[dict], messages: list[dict]
    ) -> Response:
        messages_by_convo: dict[str, list] = defaultdict(list)
        for m in messages:
            messages_by_convo[m["conversation_id"]].append(
                {
                    "role": m["role"],
                    "content": m["content"],
                    "created_at": m["created_at"],
                }
            )
        payload = {
            "agent_id": agent_id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.analytics_service.compute(agent_id).model_dump(
                mode="json"
            ),
            "conversations": [
                {**c, "messages": messages_by_convo.get(c["id"], [])}
                for c in conversations
            ],
        }
        body = json.dumps(payload, default=str, indent=2)
        return Response(
            content=body,
            media_type="application/json",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="agent_{agent_id}_export.json"'
                )
            },
        )
