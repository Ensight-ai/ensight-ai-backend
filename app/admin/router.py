"""Admin routes: founder metrics + user management (restricted to ADMIN_EMAILS)."""

from fastapi import APIRouter, Depends, Query, status

from app.admin.dependencies import get_admin_service
from app.admin.schemas import (
    AdminMetrics,
    AdminPayments,
    AdminUserDetail,
    SetPlanRequest,
)
from app.admin.service import AdminService
from app.core.pagination import Page, PageParams
from app.dependencies import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/access")
def access(_admin=Depends(require_admin)):
    """Cheap check the frontend uses to gate the admin area."""
    return {"ok": True}


@router.get("/metrics", response_model=AdminMetrics)
def metrics(
    _admin=Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
):
    return service.metrics()


@router.get("/payments", response_model=AdminPayments)
def payments(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    _admin=Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
):
    return service.list_payments(page, per_page)


@router.get("/users", response_model=Page[AdminUserDetail])
def list_users(
    search: str | None = Query(None),
    params: PageParams = Depends(),
    _admin=Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
):
    items, total = service.list_users(search, params.limit, params.offset)
    return Page(
        items=items, total=total, limit=params.limit, offset=params.offset
    )


@router.patch("/users/{user_id}", response_model=AdminUserDetail)
def set_user_plan(
    user_id: str,
    payload: SetPlanRequest,
    _admin=Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
):
    return service.set_user_plan(user_id, payload.plan)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    _admin=Depends(require_admin),
    service: AdminService = Depends(get_admin_service),
):
    service.delete_user(user_id)
