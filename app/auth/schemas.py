"""Request/response models for authentication and user profiles."""

from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class Plan(str, Enum):
    """The subscription plans a user can be on."""

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
