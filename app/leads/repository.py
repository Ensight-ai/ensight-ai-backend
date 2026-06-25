"""Data access for the ``leads`` table."""

from supabase import Client

from app.leads.schemas import LeadFilters


class LeadRepository:
    _TABLE = "leads"

    def __init__(self, db: Client) -> None:
        self.db = db

    def upsert(self, record: dict) -> dict | None:
        """Insert or update the lead for a conversation.

        One lead per conversation: re-qualifying overwrites the previous row
        (the table has a unique constraint on ``conversation_id``).
        """
        result = (
            self.db.table(self._TABLE)
            .upsert(record, on_conflict="conversation_id")
            .execute()
        )
        return result.data[0] if result.data else None

    def get_owned(self, lead_id: str, user_id: str) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .select("*")
            .eq("id", lead_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def list_filtered(
        self, user_id: str, filters: LeadFilters, limit: int, offset: int
    ) -> tuple[list[dict], int]:
        """One page of the user's leads, narrowed by the given filters.

        Ordered by score (best first) so the most promising leads surface at
        the top.
        """
        query = (
            self.db.table(self._TABLE)
            .select("*", count="exact")
            .eq("user_id", user_id)
        )
        if filters.status is not None:
            query = query.eq("status", filters.status.value)
        if filters.min_score > 0:
            query = query.gte("score", filters.min_score)
        if filters.agent_id is not None:
            query = query.eq("agent_id", filters.agent_id)
        if filters.flagged is not None:
            query = query.eq("flagged", filters.flagged)

        result = (
            query.order("score", desc=True)
            .order("updated_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data, result.count or 0
