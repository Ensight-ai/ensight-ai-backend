"""Data access for the ``conversations`` table."""

from datetime import datetime, timezone

from supabase import Client


class ConversationRepository:
    _TABLE = "conversations"

    def __init__(self, db: Client) -> None:
        self.db = db

    def create(
        self, *, agent_id: str, user_id: str, visitor_id: str, channel: str = "chat"
    ) -> dict:
        result = (
            self.db.table(self._TABLE)
            .insert(
                {
                    "agent_id": agent_id,
                    "user_id": user_id,
                    "visitor_id": visitor_id,
                    "channel": channel,
                }
            )
            .execute()
        )
        return result.data[0]

    def get_owned(self, conversation_id: str, agent_id: str) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .select("*")
            .eq("id", conversation_id)
            .eq("agent_id", agent_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def list_by_agent(self, agent_id: str) -> list[dict]:
        """All conversations for an agent (used by analytics / exports)."""
        result = (
            self.db.table(self._TABLE)
            .select("*")
            .eq("agent_id", agent_id)
            .order("started_at", desc=True)
            .execute()
        )
        return result.data

    def page_by_agent(
        self, agent_id: str, limit: int, offset: int
    ) -> tuple[list[dict], int]:
        """One page of an agent's conversations plus the total count."""
        result = (
            self.db.table(self._TABLE)
            .select("*", count="exact")
            .eq("agent_id", agent_id)
            .order("started_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data, result.count or 0

    def get_language(self, conversation_id: str) -> str | None:
        result = (
            self.db.table(self._TABLE)
            .select("language")
            .eq("id", conversation_id)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0].get("language")
        return None

    def set_language(self, conversation_id: str, language: str) -> None:
        self.db.table(self._TABLE).update({"language": language}).eq(
            "id", conversation_id
        ).execute()

    def touch(self, conversation_id: str) -> None:
        """Bump the conversation's last-activity timestamp."""
        self.db.table(self._TABLE).update(
            {"last_message_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", conversation_id).execute()
