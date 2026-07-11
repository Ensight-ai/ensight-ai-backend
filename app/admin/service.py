"""Aggregate founder-facing metrics from the app's data + Paystack."""

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from supabase import Client

from app.admin.schemas import (
    AdminMetrics,
    AdminPayment,
    AdminPayments,
    AdminUserDetail,
    AdminUserRow,
)
from app.auth.schemas import Plan
from app.billing.client import PaystackClient
from app.core.config import settings

_PAID = {Plan.starter.value, Plan.beta.value, Plan.pro.value}


class AdminService:
    def __init__(self, db: Client, paystack: PaystackClient) -> None:
        self.db = db
        self.paystack = paystack

    def _count(self, table: str, **eq) -> int:
        q = self.db.table(table).select("id", count="exact")
        for col, val in eq.items():
            q = q.eq(col, val)
        return q.limit(1).execute().count or 0

    def metrics(self) -> AdminMetrics:
        profiles = self.db.table("profiles").select("*").execute().data
        agents = self.db.table("agents").select("id,user_id").execute().data

        # Agents per owner.
        agents_by_user: Counter[str] = Counter(a["user_id"] for a in agents)
        agent_owner = {a["id"]: a["user_id"] for a in agents}

        plan_counts: Counter[str] = Counter(
            (p.get("plan") or "inactive") for p in profiles
        )
        paid_users = sum(plan_counts[p] for p in _PAID)

        # Active owners: had a conversation in the last 30 days.
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        recent_convos = (
            self.db.table("conversations")
            .select("agent_id")
            .gte("started_at", cutoff)
            .execute()
            .data
        )
        active_users = {
            agent_owner.get(c["agent_id"])
            for c in recent_convos
            if agent_owner.get(c["agent_id"])
        }

        # Estimated MRR from current paid plans (prices are kobo -> naira).
        price = {
            Plan.starter.value: settings.paystack_amount_starter // 100,
            Plan.beta.value: settings.paystack_amount_beta // 100,
            Plan.pro.value: settings.paystack_amount_pro // 100,
        }
        estimated_mrr = sum(plan_counts[p] * price[p] for p in _PAID)

        # Actual money collected (Paystack, best-effort).
        revenue_collected = total_transactions = None
        totals = self.paystack.totals()
        if totals:
            vol = totals.get("total_volume")
            if isinstance(vol, (int, float)):
                revenue_collected = int(vol) // 100  # kobo -> naira
            total_transactions = totals.get("total_transactions")

        recent_users = [
            AdminUserRow(
                email=p.get("email", ""),
                plan=p.get("plan", "inactive"),
                agents=agents_by_user.get(p["id"], 0),
                created_at=p.get("created_at"),
            )
            for p in sorted(
                profiles, key=lambda r: r.get("created_at") or "", reverse=True
            )[:15]
        ]

        return AdminMetrics(
            total_signups=len(profiles),
            paid_users=paid_users,
            active_users_30d=len(active_users),
            plan_breakdown=dict(plan_counts),
            total_agents=len(agents),
            total_conversations=self._count("conversations"),
            total_leads=self._count("leads"),
            total_bookings=self._count("bookings", status="confirmed"),
            estimated_mrr=estimated_mrr,
            revenue_collected=revenue_collected,
            total_transactions=total_transactions,
            recent_users=recent_users,
        )

    # --- user management --------------------------------------------------
    def _agent_counts(self) -> Counter:
        agents = self.db.table("agents").select("user_id").execute().data
        return Counter(a["user_id"] for a in agents)

    def list_users(
        self, search: str | None, limit: int, offset: int
    ) -> tuple[list[AdminUserDetail], int]:
        query = self.db.table("profiles").select("*", count="exact")
        if search:
            query = query.ilike("email", f"%{search}%")
        res = (
            query.order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        counts = self._agent_counts()
        items = [
            AdminUserDetail(
                id=r["id"],
                email=r.get("email", ""),
                plan=r.get("plan", "inactive"),
                agents=counts.get(r["id"], 0),
                created_at=r.get("created_at"),
            )
            for r in res.data
        ]
        return items, res.count or 0

    def set_user_plan(self, user_id: str, plan: Plan) -> AdminUserDetail:
        res = (
            self.db.table("profiles")
            .update({"plan": plan.value})
            .eq("id", user_id)
            .execute()
        )
        if not res.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        r = res.data[0]
        agents = (
            self.db.table("agents")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        return AdminUserDetail(
            id=r["id"],
            email=r.get("email", ""),
            plan=r.get("plan", "inactive"),
            agents=agents.count or 0,
            created_at=r.get("created_at"),
        )

    def delete_user(self, user_id: str) -> None:
        """Delete the auth user; the profile + agents cascade via FK."""
        try:
            self.db.auth.admin.delete_user(user_id)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=getattr(exc, "message", None) or str(exc),
            )

    # --- payments (Paystack) ----------------------------------------------
    def list_payments(self, page: int, per_page: int) -> AdminPayments:
        body = self.paystack.list_transactions(page=page, per_page=per_page)
        meta = body.get("meta") or {}
        items = []
        for t in body.get("data") or []:
            amount = t.get("amount")
            items.append(
                AdminPayment(
                    reference=t.get("reference", ""),
                    email=(t.get("customer") or {}).get("email"),
                    amount=int(amount) // 100
                    if isinstance(amount, (int, float))
                    else 0,
                    currency=t.get("currency", "NGN"),
                    status=t.get("status", ""),
                    channel=t.get("channel"),
                    paid_at=t.get("paid_at") or t.get("created_at"),
                )
            )
        return AdminPayments(
            items=items,
            total=meta.get("total", len(items)),
            page=page,
            per_page=per_page,
        )
