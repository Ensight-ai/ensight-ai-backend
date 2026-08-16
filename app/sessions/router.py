"""Agent session routes: creation and visitor-driven finalization."""

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.dependencies import get_agent_session
from app.leads.dependencies import get_lead_service
from app.leads.service import LeadService
from app.sessions.dependencies import get_session_service
from app.sessions.schemas import (
    AgentSession,
    EndSessionResponse,
    SessionRequest,
    SessionResponse,
)
from app.sessions.service import SessionService


class SessionController:
    def __init__(
        self, service: SessionService = Depends(get_session_service)
    ) -> None:
        self.service = service

    def create(self, payload: SessionRequest) -> SessionResponse:
        return self.service.create_session(payload)


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse)
def create_session(
    payload: SessionRequest, controller: SessionController = Depends()
):
    return controller.create(payload)


@router.post(
    "/end",
    response_model=EndSessionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def end_session(
    background_tasks: BackgroundTasks,
    session: AgentSession = Depends(get_agent_session),
    lead_service: LeadService = Depends(get_lead_service),
):
    """End a widget session and automatically qualify its conversation."""
    lead_service.end_conversation(session)
    background_tasks.add_task(lead_service.process_ended_conversation, session)
    return EndSessionResponse(conversation_id=session.conversation_id)
