"""Founder metrics dashboard models."""

from pydantic import BaseModel

from app.auth.schemas import Plan


class AdminUserDetail(BaseModel):
    id: str
    email: str
    plan: str
    agents: int
    created_at: str | None = None


class SetPlanRequest(BaseModel):
    plan: Plan


class AdminPayment(BaseModel):
    reference: str
    email: str | None = None
    amount: int  # in the main currency unit (e.g. naira)
    currency: str = "NGN"
    status: str
    channel: str | None = None
    paid_at: str | None = None


class AdminPayments(BaseModel):
    items: list[AdminPayment]
    total: int
    page: int
    per_page: int


class AdminUserRow(BaseModel):
    email: str
    plan: str
    agents: int
    created_at: str | None = None


class AdminMetrics(BaseModel):
    # People
    total_signups: int
    paid_users: int
    active_users_30d: int  # owners whose agents had a conversation in 30 days
    plan_breakdown: dict[str, int]  # {inactive, starter, beta, pro}

    # Product
    total_agents: int
    total_conversations: int
    total_leads: int
    total_bookings: int

    # Money (NGN)
    estimated_mrr: int  # sum of current paid plans × their price
    revenue_collected: int | None = None  # actual, from Paystack (naira)
    total_transactions: int | None = None

    # Recent signups
    recent_users: list[AdminUserRow]
