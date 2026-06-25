"""Lead routes: qualify a conversation, list/filter and fetch leads (owner-only)."""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.core.pagination import Page, PageParams
from app.dependencies import get_current_user
from app.leads.dependencies import get_lead_service
from app.leads.schemas import Lead, LeadFilters
from app.leads.service import LeadService


class QualifyRequest(BaseModel):
    agent_id: str
    conversation_id: str


class LeadController:
    def __init__(self, service: LeadService = Depends(get_lead_service)) -> None:
        self.service = service

    def qualify(self, user_id: str, payload: QualifyRequest) -> Lead:
        return self.service.qualify_conversation(
            user_id, payload.agent_id, payload.conversation_id
        )

    def list(
        self, user_id: str, filters: LeadFilters, params: PageParams
    ) -> Page[Lead]:
        return self.service.list_leads(user_id, filters, params)

    def get(self, lead_id: str, user_id: str) -> Lead:
        return self.service.get_lead(lead_id, user_id)


router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("/qualify", response_model=Lead, status_code=status.HTTP_201_CREATED)
def qualify_lead(
    payload: QualifyRequest,
    current_user=Depends(get_current_user),
    controller: LeadController = Depends(),
):
    return controller.qualify(current_user.id, payload)


@router.get("", response_model=Page[Lead])
def list_leads(
    current_user=Depends(get_current_user),
    filters: LeadFilters = Depends(),
    params: PageParams = Depends(),
    controller: LeadController = Depends(),
):
    return controller.list(current_user.id, filters, params)


@router.get("/{lead_id}", response_model=Lead)
def get_lead(
    lead_id: str,
    current_user=Depends(get_current_user),
    controller: LeadController = Depends(),
):
    return controller.get(lead_id, current_user.id)
