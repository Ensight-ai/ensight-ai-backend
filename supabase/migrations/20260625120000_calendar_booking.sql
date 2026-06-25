-- Google Calendar booking: per-owner Google connection, bookings, agent toggles.

-- One Google connection per ensight user (the business owner). Stores the
-- OAuth tokens used to read availability and create events on their calendar.
-- NOTE: tokens are sensitive; the backend uses the service-role key and RLS is
-- enabled so the anon key can't read them. Consider encrypting at rest in prod.
create table if not exists public.google_connections (
    user_id            uuid primary key references auth.users (id) on delete cascade,
    google_email       text,
    access_token       text not null,
    refresh_token      text not null,
    token_expiry       timestamptz not null,
    scope              text,
    calendar_timezone  text,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);

-- Meetings the agent booked on an owner's calendar with a visitor.
create table if not exists public.bookings (
    id              uuid primary key default gen_random_uuid(),
    user_id         uuid not null references auth.users (id) on delete cascade,
    agent_id        uuid not null references public.agents (id) on delete cascade,
    conversation_id uuid references public.conversations (id) on delete set null,
    visitor_name    text,
    visitor_email   text not null,
    visitor_phone   text,
    start_time      timestamptz not null,
    end_time        timestamptz not null,
    meet_link       text,
    -- Google Calendar event id (so we can cancel/update later).
    event_id        text,
    status          text not null default 'confirmed'
                      check (status in ('confirmed', 'cancelled')),
    created_at      timestamptz not null default now()
);

create index if not exists bookings_user_id_idx on public.bookings (user_id);
create index if not exists bookings_agent_id_idx on public.bookings (agent_id);
create index if not exists bookings_start_time_idx on public.bookings (start_time);

-- Per-agent booking toggle + meeting length. Booking only happens when the
-- owner has connected Google AND enabled it on the agent.
alter table public.agents
    add column if not exists booking_enabled boolean not null default false;
alter table public.agents
    add column if not exists meeting_duration_minutes int not null default 30;

-- RLS on (service-role key bypasses it; anon key cannot read these).
alter table public.google_connections enable row level security;
alter table public.bookings enable row level security;

-- Keep updated_at fresh on google_connections writes (function added in the
-- prior migration; create it if running this one standalone).
create or replace function public.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists google_connections_set_updated_at on public.google_connections;
create trigger google_connections_set_updated_at
    before update on public.google_connections
    for each row execute function public.set_updated_at();
