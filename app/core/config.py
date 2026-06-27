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

    # --- Google Calendar booking ------------------------------------------
    # ensight's single OAuth client (Web application). Businesses connect their
    # own Google account through it; the secret stays server-side.
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    # Must exactly match an authorized redirect URI on the OAuth client.
    google_oauth_redirect_uri: str = (
        "http://localhost:8000/integrations/google/callback"
    )
    # Where to send the owner's browser after connecting/failing (dashboard).
    frontend_url: str = "http://localhost:3000"

    # Default meeting settings (per-agent overrides can come later).
    booking_meeting_minutes: int = 30
    # Working-hours window slots are suggested within (owner's calendar tz).
    booking_workday_start_hour: int = 9
    booking_workday_end_hour: int = 17
    # How many days ahead to look for availability.
    booking_lookahead_days: int = 5

    # --- Paystack billing -------------------------------------------------
    # Secret key (sk_test_... / sk_live_...). Stays server-side.
    paystack_secret_key: str = ""
    paystack_base_url: str = "https://api.paystack.co"
    # Subscription plan codes (created in the Paystack dashboard). Defaults are
    # the test-mode plans; override per environment via env vars.
    paystack_plan_starter: str = "PLN_jd8vdz79mg39a4r"
    paystack_plan_beta: str = "PLN_6cq4diiuojdy715"
    paystack_plan_pro: str = "PLN_hgysxnd84bzx5bc"
    # Plan prices in the smallest currency unit (kobo for NGN). Must match the
    # amounts configured on the Paystack plans: ₦8,000 / ₦22,000 / ₦34,500.
    paystack_currency: str = "NGN"
    paystack_amount_starter: int = 800000
    paystack_amount_beta: int = 2200000
    paystack_amount_pro: int = 3450000


settings = Settings()
