"""Request/response models for authentication and user profiles."""

from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class Plan(str, Enum):
    """The subscription plans a user can be on.

    ``inactive`` is the default for a brand-new account that hasn't subscribed
    yet — it unlocks nothing, so the user must pick and pay for a plan first.
    """

    inactive = "inactive"
    starter = "starter"
    beta = "beta"
    pro = "pro"


class SignUpRequest(BaseModel):
    email: EmailStr
    # bcrypt (used by Supabase) caps passwords at 72 bytes.
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenRequest(BaseModel):
    """A verification/reset token from an emailed link."""

    token: str


class EmailRequest(BaseModel):
    """Just an email — for resend-verification and forgot-password."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=72)


class MessageResponse(BaseModel):
    message: str


class UserProfile(BaseModel):
    id: str
    email: EmailStr
    plan: Plan = Plan.starter


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserProfile


class SignUpResponse(BaseModel):
    user: UserProfile
    # Null when Supabase requires email confirmation before issuing a session.
    access_token: str | None = None
    refresh_token: str | None = None
    message: str
