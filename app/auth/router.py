"""Authentication routes: signup, login, current-user profile."""

from fastapi import APIRouter, Depends, status

from app.auth.dependencies import get_auth_service
from app.auth.schemas import (
    AuthResponse,
    EmailRequest,
    LoginRequest,
    MessageResponse,
    ResetPasswordRequest,
    SignUpRequest,
    SignUpResponse,
    TokenRequest,
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

    def verify_email(self, payload: TokenRequest) -> MessageResponse:
        return self.service.verify_email(payload.token)

    def resend_verification(self, payload: EmailRequest) -> MessageResponse:
        return self.service.resend_verification(payload.email)

    def forgot_password(self, payload: EmailRequest) -> MessageResponse:
        return self.service.request_password_reset(payload.email)

    def reset_password(self, payload: ResetPasswordRequest) -> MessageResponse:
        return self.service.reset_password(payload.token, payload.password)


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


@router.post("/verify-email", response_model=MessageResponse)
def verify_email(payload: TokenRequest, controller: AuthController = Depends()):
    return controller.verify_email(payload)


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(
    payload: EmailRequest, controller: AuthController = Depends()
):
    return controller.resend_verification(payload)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: EmailRequest, controller: AuthController = Depends()):
    return controller.forgot_password(payload)


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    payload: ResetPasswordRequest, controller: AuthController = Depends()
):
    return controller.reset_password(payload)
