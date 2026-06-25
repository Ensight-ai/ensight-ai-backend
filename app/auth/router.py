"""Authentication routes: signup, login, current-user profile."""

from fastapi import APIRouter, Depends, status

from app.auth.dependencies import get_auth_service
from app.auth.schemas import (
    AuthResponse,
    LoginRequest,
    SignUpRequest,
    SignUpResponse,
    UserProfile,
)
from app.auth.service import AuthService
from app.dependencies import get_current_user


class AuthController:
    """Handlers for the auth feature; its service is injected via DI."""

    def __init__(self, service: AuthService = Depends(get_auth_service)) -> None:
        self.service = service

    def signup(self, payload: SignUpRequest) -> SignUpResponse:
        return self.service.signup(payload)

    def login(self, payload: LoginRequest) -> AuthResponse:
        return self.service.login(payload)

    def me(self, current_user) -> UserProfile:
        return self.service.get_profile(current_user.id, current_user.email)


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup", response_model=SignUpResponse, status_code=status.HTTP_201_CREATED
)
def signup(payload: SignUpRequest, controller: AuthController = Depends()):
    return controller.signup(payload)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, controller: AuthController = Depends()):
    return controller.login(payload)


@router.get("/me", response_model=UserProfile)
def me(
    current_user=Depends(get_current_user),
    controller: AuthController = Depends(),
):
    return controller.me(current_user)
