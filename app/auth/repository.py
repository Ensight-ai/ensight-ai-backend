"""Data access for the ``profiles`` table."""

from supabase import Client


class AuthRepository:
    _TABLE = "profiles"

    def __init__(self, db: Client) -> None:
        self.db = db

    def get(self, user_id: str) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .select("*")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def create(self, *, user_id: str, email: str, plan: str) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .insert({"id": user_id, "email": email, "plan": plan})
            .execute()
        )
        return result.data[0] if result.data else None
