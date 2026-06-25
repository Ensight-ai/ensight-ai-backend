"""Data access for the ``messages`` table."""

from collections import defaultdict

from supabase import Client


class MessageRepository:
    _TABLE = "messages"

    def __init__(self, db: Client) -> None:
        self.db = db

    def add(
        self, *, conversation_id: str, agent_id: str, role: str, content: str
    ) -> None:
        self.db.table(self._TABLE).insert(
            {
                "conversation_id": conversation_id,
                "agent_id": agent_id,
                "role": role,
                "content": content,
            }
        ).execute()

    def history(self, conversation_id: str) -> list[dict]:
        """Prior turns as ``[{"role","content"}, ...]`` oldest first."""
        result = (
            self.db.table(self._TABLE)
            .select("role,content")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute()
        )
        return result.data

    def list_by_conversation(self, conversation_id: str) -> list[dict]:
        result = (
            self.db.table(self._TABLE)
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at")
            .execute()
        )
        return result.data

    def list_by_agent(self, agent_id: str, columns: str = "*") -> list[dict]:
        result = (
            self.db.table(self._TABLE)
            .select(columns)
            .eq("agent_id", agent_id)
            .execute()
        )
        return result.data

    def counts_for_conversations(
        self, conversation_ids: list[str]
    ) -> dict[str, int]:
        """Message count per conversation, for just the given ids."""
        if not conversation_ids:
            return {}
        result = (
            self.db.table(self._TABLE)
            .select("conversation_id")
            .in_("conversation_id", conversation_ids)
            .execute()
        )
        counts: dict[str, int] = defaultdict(int)
        for row in result.data:
            counts[row["conversation_id"]] += 1
        return dict(counts)

    def recent_questions(self, agent_id: str, limit: int = 10) -> list[str]:
        result = (
            self.db.table(self._TABLE)
            .select("content")
            .eq("agent_id", agent_id)
            .eq("role", "user")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [row["content"] for row in result.data]
