"""Export routes (owner-only): download an agent's full data."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.dependencies import get_current_user
from app.exports.dependencies import get_export_service
from app.exports.service import ExportService


class ExportController:
    def __init__(
        self, service: ExportService = Depends(get_export_service)
    ) -> None:
        self.service = service

    def export(self, agent_id: str, user_id: str, fmt: str) -> Response:
        return self.service.export_agent(agent_id, user_id, fmt)


router = APIRouter(prefix="/agents", tags=["exports"])


@router.get("/{agent_id}/export")
def export_agent(
    agent_id: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    current_user=Depends(get_current_user),
    controller: ExportController = Depends(),
):
    return controller.export(agent_id, current_user.id, format)
