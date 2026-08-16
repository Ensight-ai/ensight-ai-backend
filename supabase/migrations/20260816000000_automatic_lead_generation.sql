-- Automatically qualify leads when a visitor conversation ends.

-- Conversation lifecycle and worker state. The processing state makes the
-- end-session endpoint idempotent when close/pagehide requests race.
alter table public.conversations
    add column if not exists ended_at timestamptz;
alter table public.conversations
    add column if not exists lead_processing_status text not null default 'active';
alter table public.conversations
    add column if not exists lead_qualified_at timestamptz;

alter table public.conversations
    drop constraint if exists conversations_lead_processing_status_check;
alter table public.conversations
    add constraint conversations_lead_processing_status_check
    check (lead_processing_status in (
        'active', 'pending', 'processing', 'completed', 'failed'
    ));

create index if not exists conversations_lead_processing_idx
    on public.conversations (lead_processing_status, ended_at);

-- A warm/hot lead alert is sent at most once per conversation.
alter table public.leads
    add column if not exists alert_sent_at timestamptz;

