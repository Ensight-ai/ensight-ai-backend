"""Auth + user-profile business logic (Supabase Auth + profiles table)."""

from fastapi import HTTPException, status
from supabase import Client

from app.auth.repository import AuthRepository
from app.auth.schemas import (
    AuthResponse,
    LoginRequest,
    Plan,
    SignUpRequest,
    SignUpResponse,
    UserProfile,
)


def _error_message(exc: Exception) -> str:
    return getattr(exc, "message", None) or str(exc)


class AuthService:
    def __init__(
        self, repository: AuthRepository, supabase: Client, admin: Client
    ) -> None:
        self.repository = repository
        # Publishable client — used for sign-in (password -> session tokens).
        self.supabase = supabase
        # Secret client — used for admin user creation (no confirmation email).
        self.admin = admin

    # --- profiles ---------------------------------------------------------
    def get_profile(self, user_id: str, fallback_email: str = "") -> UserProfile:
        row = self.repository.get(user_id)
        if row:
            return UserProfile(
                id=user_id,
                email=row.get("email", fallback_email),
                plan=row.get("plan", Plan.starter),
            )
        # No profile row yet — treat as a starter user.
        return UserProfile(id=user_id, email=fallback_email, plan=Plan.starter)

    def get_plan(self, user_id: str) -> Plan:
        return self.get_profile(user_id).plan

    def _create_starter_profile(self, user_id: str, email: str) -> None:
        self.repository.create(
            user_id=user_id, email=email, plan=Plan.starter.value
        )

    # --- auth -------------------------------------------------------------
    def signup(self, payload: SignUpRequest) -> SignUpResponse:
        """Register a new user and create their starter-plan profile.

        Uses the admin API with ``email_confirm=True`` so no confirmation email
        is sent (avoids Supabase's email rate limit) and the user can log in
        immediately. We then sign in to return session tokens.
        """
        try:
            result = self.admin.auth.admin.create_user(
                {
                    "email": payload.email,
                    "password": payload.password,
                    "email_confirm": True,
                }
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_error_message(exc),
            )

        if result.user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Sign up failed"
            )

        self._create_starter_profile(result.user.id, payload.email)
        profile = UserProfile(
            id=result.user.id, email=payload.email, plan=Plan.starter
        )

        # Immediately sign in so the client gets tokens without a separate step.
        access_token = refresh_token = None
        try:
            signin = self.supabase.auth.sign_in_with_password(
                {"email": payload.email, "password": payload.password}
            )
            if signin.session:
                access_token = signin.session.access_token
                refresh_token = signin.session.refresh_token
        except Exception:
            pass

        return SignUpResponse(
            user=profile,
            access_token=access_token,
            refresh_token=refresh_token,
            message="Account created.",
        )

    def login(self, payload: LoginRequest) -> AuthResponse:
        """Authenticate with email + password and return access tokens."""
        try:
            result = self.supabase.auth.sign_in_with_password(
                {"email": payload.email, "password": payload.password}
            )
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if result.session is None or result.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        return AuthResponse(
            access_token=result.session.access_token,
            refresh_token=result.session.refresh_token,
            user=self.get_profile(result.user.id, payload.email),
        )
