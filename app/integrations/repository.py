"""Data access for the ``google_connections`` table."""

from supabase import Client


class GoogleConnectionRepository:
    _TABLE = "google_connections"

    def __init__(self, db: Client) -> None:
        self.db = db

    def get(self, user_id: str) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def upsert(self, record: dict) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .upsert(record, on_conflict="user_id")
            .execute()
        )
        return result.data[0] if result.data else None

    def update(self, user_id: str, updates: dict) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .update(updates)
            .eq("user_id", user_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def delete(self, user_id: str) -> None:
        self.db.table(self._TABLE).delete().eq("user_id", user_id).execute()
