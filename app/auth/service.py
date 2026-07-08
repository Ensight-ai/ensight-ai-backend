"""Auth + user-profile business logic (Supabase Auth + profiles table)."""

import jwt
from fastapi import HTTPException, status
from supabase import Client

from app.auth.repository import AuthRepository
from app.auth.schemas import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    Plan,
    SignUpRequest,
    SignUpResponse,
    UserProfile,
)
from app.core import mailer
from app.core.security import create_email_token, decode_email_token


def _error_message(exc: Exception) -> str:
    return getattr(exc, "message", None) or str(exc)


# Generic message so we never reveal whether an email is registered.
_GENERIC_EMAIL_SENT = (
    "If an account exists for that email, we've sent a link. Please check "
    "your inbox."
)


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
                plan=row.get("plan", Plan.inactive),
            )
        # No profile row yet — treat as inactive (must subscribe first).
        return UserProfile(id=user_id, email=fallback_email, plan=Plan.inactive)

    def get_plan(self, user_id: str) -> Plan:
        return self.get_profile(user_id).plan

    def _create_inactive_profile(self, user_id: str, email: str) -> None:
        # New accounts start with no active plan; they must subscribe to use
        # the product (hard paywall). Payment flips this via the billing flow.
        self.repository.create(
            user_id=user_id, email=email, plan=Plan.inactive.value
        )

    # --- auth -------------------------------------------------------------
    def signup(self, payload: SignUpRequest) -> SignUpResponse:
        """Register a new user (unconfirmed) and email a verification link.

        The account is created with ``email_confirm=False`` so the user can't
        sign in until they click the link we email via ZeptoMail. No session
        tokens are returned at signup.
        """
        try:
            result = self.admin.auth.admin.create_user(
                {
                    "email": payload.email,
                    "password": payload.password,
                    "email_confirm": False,
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

        self._create_inactive_profile(result.user.id, payload.email)
        profile = UserProfile(
            id=result.user.id, email=payload.email, plan=Plan.inactive
        )

        self._send_verification(result.user.id, payload.email)

        return SignUpResponse(
            user=profile,
            access_token=None,
            refresh_token=None,
            message=(
                "Account created. We've emailed you a link to confirm your "
                "email address — please check your inbox."
            ),
        )

    def login(self, payload: LoginRequest) -> AuthResponse:
        """Authenticate with email + password and return access tokens.

        Rejects users whose email hasn't been confirmed yet.
        """
        try:
            result = self.supabase.auth.sign_in_with_password(
                {"email": payload.email, "password": payload.password}
            )
        except Exception:
            # Supabase blocks unconfirmed logins when confirmation is required.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password. If you just signed up, "
                "confirm your email first.",
            )

        if result.session is None or result.user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Enforce verification ourselves too (in case Supabase's confirm-email
        # setting is off): reject sign-in until the email is confirmed.
        confirmed_at = getattr(result.user, "email_confirmed_at", None) or getattr(
            result.user, "confirmed_at", None
        )
        if not confirmed_at:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please confirm your email before signing in.",
            )

        return AuthResponse(
            access_token=result.session.access_token,
            refresh_token=result.session.refresh_token,
            user=self.get_profile(result.user.id, payload.email),
        )

    # --- email verification ----------------------------------------------
    def _send_verification(self, user_id: str, email: str) -> None:
        token = create_email_token(purpose="verify", user_id=user_id, email=email)
        try:
            mailer.send_verification_email(email, token)
        except mailer.MailError:
            # Don't fail signup on a transient email error; user can resend.
            pass

    def verify_email(self, token: str) -> MessageResponse:
        try:
            payload = decode_email_token(token, purpose="verify")
        except (jwt.PyJWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This verification link is invalid or has expired.",
            )
        try:
            self.admin.auth.admin.update_user_by_id(
                payload["sub"], {"email_confirm": True}
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_error_message(exc),
            )
        return MessageResponse(message="Your email has been confirmed.")

    def resend_verification(self, email: str) -> MessageResponse:
        row = self.repository.get_by_email(email)
        if row:
            self._send_verification(row["id"], email)
        return MessageResponse(message=_GENERIC_EMAIL_SENT)

    # --- password reset ---------------------------------------------------
    def request_password_reset(self, email: str) -> MessageResponse:
        row = self.repository.get_by_email(email)
        if row:
            token = create_email_token(
                purpose="reset", user_id=row["id"], email=email
            )
            try:
                mailer.send_password_reset_email(email, token)
            except mailer.MailError:
                pass
        return MessageResponse(message=_GENERIC_EMAIL_SENT)

    def reset_password(self, token: str, new_password: str) -> MessageResponse:
        try:
            payload = decode_email_token(token, purpose="reset")
        except (jwt.PyJWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This reset link is invalid or has expired.",
            )
        try:
            self.admin.auth.admin.update_user_by_id(
                payload["sub"], {"password": new_password}
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=_error_message(exc),
            )
        return MessageResponse(
            message="Your password has been reset. You can now sign in."
        )
