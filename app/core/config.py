"""Application settings, loaded from environment / .env."""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Supabase project URL, e.g. https://xxxx.supabase.co
    supabase_url: str = ""
    # Publishable (public) key — used for auth flows (signup / login).
    # Supabase's newer "publishable_key"; the old "anon key" also works.
    supabase_publishable_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY"
        ),
    )
    # Secret key — used by the trusted backend for table writes and validating
    # user tokens; bypasses RLS. Never expose to clients. Supabase's newer
    # "secret key"; the old "service_role key" also works.
    supabase_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_KEY"
        ),
    )

    # Secret used to sign short-lived agent *session* tokens (the ones a
    # public website widget gets in exchange for an agent's public key).
    # Override this in production with a long random value.
    session_secret: str = "change-me-in-production"
    # How long an issued session token stays valid.
    session_token_ttl_minutes: int = 60

    # Voice agent (Google Cloud Speech-to-Text / Text-to-Speech).
    voice_language_code: str = "en-US"
    # Specific TTS voice name (e.g. "en-US-Neural2-C"). Empty -> Google picks
    # a default voice for the language.
    voice_name: str = ""


settings = Settings()
