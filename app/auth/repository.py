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

    def get_by_email(self, email: str) -> dict | None:
        result = (
            self.db.table(self._TABLE)
            .select("*")
            .eq("email", email)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def set_plan(self, user_id: str, plan: str) -> dict | None:
        """Update the existing ``plan`` column — no schema change needed."""
        result = (
            self.db.table(self._TABLE)
            .update({"plan": plan})
            .eq("id", user_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def set_plan_by_email(self, email: str, plan: str) -> dict | None:
        """Used by the payment webhook, which identifies the user by email."""
        result = (
            self.db.table(self._TABLE)
            .update({"plan": plan})
            .eq("email", email)
            .execute()
        )
        return result.data[0] if result.data else None
