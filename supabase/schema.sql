-- Ensight AI — database schema
-- Run this in the Supabase SQL editor (Dashboard > SQL Editor > New query).
-- Supabase already provides the auth.users table; we link to it below.

-- The plans a user can be on. 'inactive' = signed up but not yet subscribed
-- (hard paywall); starter/beta/pro are the paid tiers.
do $$
begin
    if not exists (select 1 from pg_type where typname = 'plan') then
        create type plan as enum ('inactive', 'starter', 'beta', 'pro');
    end if;
end$$;

-- One profile row per auth user, holding their plan.
create table if not exists public.profiles (
    id         uuid primary key references auth.users (id) on delete cascade,
    email      text not null,
    plan       plan not null default 'starter',
    created_at timestamptz not null default now()
);

-- Agents created by users. (id = agent_id, user_id = owner)
create table if not exists public.agents (
    id               uuid primary key default gen_random_uuid(),
    user_id          uuid not null references auth.users (id) on delete cascade,
    name             text not null,
    -- chat | voice | both  (gated by the owner's plan in the backend)
    capability       text not null default 'chat'
                       check (capability in ('chat', 'voice', 'both')),
    background_color text not null default '#2563eb',
    position         text not null default 'bottom-right'
                       check (position in ('bottom-left', 'bottom-right')),
    -- non-secret key embedded in the website widget
    public_key       text not null unique,
    created_at       timestamptz not null default now()
);

create index if not exists agents_user_id_idx on public.agents (user_id);

-- If you created the agents table from an earlier version, these add the new
-- columns idempotently. (Backfill public_key for existing rows before adding
-- the unique index — fresh installs already have it from the create above.)
alter table public.agents
    add column if not exists capability text not null default 'chat';
alter table public.agents
    add column if not exists background_color text not null default '#2563eb';
alter table public.agents
    add column if not exists position text not null default 'bottom-right';
alter table public.agents
    add column if not exists public_key text;
create unique index if not exists agents_public_key_key
    on public.agents (public_key);

-- Conversations: one per agent session (a visitor chatting with a bot).
create table if not exists public.conversations (
    id              uuid primary key default gen_random_uuid(),
    agent_id        uuid not null references public.agents (id) on delete cascade,
    user_id         uuid not null references auth.users (id) on delete cascade,
    visitor_id      text not null,
    channel         text not null default 'chat'
                      check (channel in ('chat', 'voice')),
    -- Detected conversation language (ISO 639-1 code, e.g. 'en', 'es').
    language        text,
    started_at      timestamptz not null default now(),
    last_message_at timestamptz,
    ended_at        timestamptz,
    lead_processing_status text not null default 'active'
                      check (lead_processing_status in (
                        'active', 'pending', 'processing', 'completed', 'failed'
                      )),
    lead_qualified_at timestamptz
);

-- If upgrading an existing conversations table:
alter table public.conversations add column if not exists language text;
alter table public.conversations add column if not exists ended_at timestamptz;
alter table public.conversations
    add column if not exists lead_processing_status text not null default 'active';
alter table public.conversations
    add column if not exists lead_qualified_at timestamptz;

create index if not exists conversations_agent_id_idx
    on public.conversations (agent_id);
create index if not exists conversations_visitor_id_idx
    on public.conversations (visitor_id);
create index if not exists conversations_lead_processing_idx
    on public.conversations (lead_processing_status, ended_at);

-- Messages within a conversation.
create table if not exists public.messages (
    id              uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references public.conversations (id) on delete cascade,
    agent_id        uuid not null references public.agents (id) on delete cascade,
    role            text not null check (role in ('user', 'assistant')),
    content         text not null,
    created_at      timestamptz not null default now()
);

create index if not exists messages_conversation_id_idx
    on public.messages (conversation_id);
create index if not exists messages_agent_id_idx
    on public.messages (agent_id);

-- Row-Level Security: the backend uses the service-role key (which bypasses
-- RLS), so these tables are safe by default — no client can read them with
-- the anon key once RLS is enabled.
alter table public.profiles enable row level security;
alter table public.agents enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
