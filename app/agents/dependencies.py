"""Providers that wire the agents feature for FastAPI dependency injection."""

from fastapi import Depends
from supabase import Client

from app.agents.repository import AgentRepository
from app.agents.service import AgentService
from app.auth.dependencies import get_auth_service
from app.auth.service import AuthService
from app.dependencies import get_db


def get_agent_repository(db: Client = Depends(get_db)) -> AgentRepository:
    return AgentRepository(db)


def get_agent_service(
    repository: AgentRepository = Depends(get_agent_repository),
    auth_service: AuthService = Depends(get_auth_service),
) -> AgentService:
    return AgentService(repository, auth_service)
