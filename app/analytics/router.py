"""Agent analytics route (owner-only)."""

from fastapi import APIRouter, Depends

from app.analytics.dependencies import get_analytics_service
from app.analytics.schemas import AgentAnalytics
from app.analytics.service import AnalyticsService
from app.dependencies import get_current_user


class AnalyticsController:
    def __init__(
        self, service: AnalyticsService = Depends(get_analytics_service)
    ) -> None:
        self.service = service

    def get(self, agent_id: str, user_id: str) -> AgentAnalytics:
        return self.service.get_analytics(agent_id, user_id)


router = APIRouter(prefix="/agents", tags=["analytics"])


@router.get("/{agent_id}/analytics", response_model=AgentAnalytics)
def agent_analytics(
    agent_id: str,
    current_user=Depends(get_current_user),
    controller: AnalyticsController = Depends(),
):
    return controller.get(agent_id, current_user.id)
