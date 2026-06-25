"""Agent routes: create, configure, list agents and ingest documents."""

from fastapi import APIRouter, Depends, UploadFile, status

from app.agents.dependencies import get_agent_service
from app.agents.schemas import Agent, AgentCreate, AgentUpdate, IngestResponse
from app.agents.service import AgentService
from app.core.pagination import Page, PageParams
from app.dependencies import get_current_user


class AgentController:
    def __init__(self, service: AgentService = Depends(get_agent_service)) -> None:
        self.service = service

    def create(self, user_id: str, payload: AgentCreate) -> Agent:
        return self.service.create_agent(user_id, payload)

    def list(self, user_id: str, params: PageParams) -> Page[Agent]:
        return self.service.list_agents(user_id, params)

    def get(self, agent_id: str, user_id: str) -> Agent:
        return self.service.get_agent(agent_id, user_id)

    def update(self, agent_id: str, user_id: str, payload: AgentUpdate) -> Agent:
        return self.service.update_agent(agent_id, user_id, payload)

    def ingest(
        self, agent_id: str, user_id: str, file: UploadFile
    ) -> IngestResponse:
        return self.service.ingest_document(agent_id, user_id, file)


router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=Agent, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    current_user=Depends(get_current_user),
    controller: AgentController = Depends(),
):
    return controller.create(current_user.id, payload)


@router.get("", response_model=Page[Agent])
def list_agents(
    current_user=Depends(get_current_user),
    params: PageParams = Depends(),
    controller: AgentController = Depends(),
):
    return controller.list(current_user.id, params)


@router.get("/{agent_id}", response_model=Agent)
def get_agent(
    agent_id: str,
    current_user=Depends(get_current_user),
    controller: AgentController = Depends(),
):
    return controller.get(agent_id, current_user.id)


@router.patch("/{agent_id}", response_model=Agent)
def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    current_user=Depends(get_current_user),
    controller: AgentController = Depends(),
):
    return controller.update(agent_id, current_user.id, payload)


@router.post(
    "/{agent_id}/documents",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_document(
    agent_id: str,
    file: UploadFile,
    current_user=Depends(get_current_user),
    controller: AgentController = Depends(),
):
    return controller.ingest(agent_id, current_user.id, file)
