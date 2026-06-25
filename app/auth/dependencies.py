"""Providers that wire the auth feature for FastAPI dependency injection."""

from fastapi import Depends
from supabase import Client

from app.auth.repository import AuthRepository
from app.auth.service import AuthService
from app.dependencies import get_auth_client, get_db


def get_auth_repository(db: Client = Depends(get_db)) -> AuthRepository:
    return AuthRepository(db)


def get_auth_service(
    repository: AuthRepository = Depends(get_auth_repository),
    supabase: Client = Depends(get_auth_client),
    admin: Client = Depends(get_db),
) -> AuthService:
    return AuthService(repository, supabase, admin)
