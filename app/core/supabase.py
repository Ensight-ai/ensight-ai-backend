"""Supabase client factories.

Two clients, two jobs:

* :func:`get_supabase` uses the *anon* key and drives auth (signup, login,
  token validation) on behalf of end users.
* :func:`get_supabase_admin` uses the *service-role* key. It bypasses
  row-level security and is used by the trusted backend to read/write tables.
  Never hand this client (or its key) to a client app.

Both are cached so we reuse one connection pool instead of rebuilding a
client per request.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.core.config import settings


@lru_cache
def get_supabase() -> Client:
    return create_client(settings.supabase_url, settings.supabase_publishable_key)


@lru_cache
def get_supabase_admin() -> Client:
    return create_client(settings.supabase_url, settings.supabase_secret_key)
