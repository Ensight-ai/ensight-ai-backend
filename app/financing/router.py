"""Financing routes: snapshot the business and assess loan readiness (owner-only)."""

from fastapi import APIRouter, Depends

from app.core.plan_guard import require_feature
from app.core.plans import Feature
from app.financing.dependencies import get_financing_service
from app.financing.schemas import (
    BusinessSnapshot,
    FinancingIntake,
    FinancingResult,
)
from app.financing.service import FinancingService


class FinancingController:
    def __init__(
        self, service: FinancingService = Depends(get_financing_service)
    ) -> None:
        self.service = service

    def snapshot(self, user_id: str) -> BusinessSnapshot:
        return self.service.build_snapshot(user_id)

    def assess(self, user_id: str, payload: FinancingIntake) -> FinancingResult:
        return self.service.assess(user_id, payload)


router = APIRouter(prefix="/financing", tags=["financing"])


@router.get("/snapshot", response_model=BusinessSnapshot)
def get_snapshot(
    current_user=Depends(require_feature(Feature.financing)),
    controller: FinancingController = Depends(),
):
    return controller.snapshot(current_user.id)


@router.post("/assess", response_model=FinancingResult)
def assess(
    payload: FinancingIntake,
    current_user=Depends(require_feature(Feature.financing)),
    controller: FinancingController = Depends(),
):
    return controller.assess(current_user.id, payload)
