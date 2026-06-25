"""Agent session route: public key -> short-lived session token."""

from fastapi import APIRouter, Depends

from app.sessions.dependencies import get_session_service
from app.sessions.schemas import SessionRequest, SessionResponse
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
