"""Data access for the ``content_drafts`` table."""

from supabase import Client

from app.content.schemas import ContentFilters


class ContentRepository:
    _TABLE = "content_drafts"

    def __init__(self, db: Client) -> None:
        self.db = db

    def create(self, record: dict) -> dict | None:
        result = self.db.table(self._TABLE).insert(record).execute()
        return result.data[0] if result.data else None

    def get_owned(self, draft_id: str, user_id: str) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .select("*")
            .eq("id", draft_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def update(self, draft_id: str, updates: dict) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .update(updates)
            .eq("id", draft_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def delete(self, draft_id: str) -> None:
        self.db.table(self._TABLE).delete().eq("id", draft_id).execute()

    def list_filtered(
        self, user_id: str, filters: ContentFilters, limit: int, offset: int
    ) -> tuple[list[dict], int]:
        query = (
            self.db.table(self._TABLE)
            .select("*", count="exact")
            .eq("user_id", user_id)
        )
        if filters.agent_id is not None:
            query = query.eq("agent_id", filters.agent_id)
        if filters.content_type is not None:
            query = query.eq("content_type", filters.content_type.value)
        if filters.status is not None:
            query = query.eq("status", filters.status.value)

        result = (
            query.order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data, result.count or 0
