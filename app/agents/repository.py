"""Data access for the ``agents`` table."""

from supabase import Client


class AgentRepository:
    _TABLE = "agents"

    def __init__(self, db: Client) -> None:
        self.db = db

    def create(self, record: dict) -> dict | None:
        result = self.db.table(self._TABLE).insert(record).execute()
        return result.data[0] if result.data else None

    def count_by_user(self, user_id: str) -> int:
        result = (
            self.db.table(self._TABLE)
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        return result.count or 0

    def get_owned(self, agent_id: str, user_id: str) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .select("*")
            .eq("id", agent_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_by_public_key(self, public_key: str) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .select("*")
            .eq("public_key", public_key)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def list_by_user(
        self, user_id: str, limit: int, offset: int
    ) -> tuple[list[dict], int]:
        """Return one page of the user's agents plus the total count."""
        result = (
            self.db.table(self._TABLE)
            .select("*", count="exact")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data, result.count or 0

    def update(self, agent_id: str, updates: dict) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .update(updates)
            .eq("id", agent_id)
            .execute()
        )
        return result.data[0] if result.data else None
