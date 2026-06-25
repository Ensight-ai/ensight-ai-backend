-- Leads (sales-lead qualification) and content drafts (writing helper).

-- Leads: one qualified lead inferred per conversation.
create table if not exists public.leads (
    id              uuid primary key default gen_random_uuid(),
    user_id         uuid not null references auth.users (id) on delete cascade,
    agent_id        uuid not null references public.agents (id) on delete cascade,
    conversation_id uuid not null references public.conversations (id) on delete cascade,
    status          text not null
                      check (status in ('hot', 'warm', 'cold', 'unqualified')),
    score           int not null default 0 check (score between 0 and 100),
    intent          text,
    summary         text,
    name            text,
    email           text,
    phone           text,
    company         text,
    confidence      double precision not null default 0,
    -- True when low-confidence and a human should review.
    flagged         boolean not null default false,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- One lead per conversation (re-qualifying upserts on this).
create unique index if not exists leads_conversation_id_key
    on public.leads (conversation_id);
create index if not exists leads_user_id_idx on public.leads (user_id);
create index if not exists leads_agent_id_idx on public.leads (agent_id);
-- Supports the "good leads" filters (by owner, then status / score).
create index if not exists leads_user_status_score_idx
    on public.leads (user_id, status, score desc);

-- Content drafts: marketing copy generated for an owner to review/edit/approve.
create table if not exists public.content_drafts (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid not null references auth.users (id) on delete cascade,
    agent_id      uuid not null references public.agents (id) on delete cascade,
    content_type  text not null
                    check (content_type in (
                      'blog_post', 'product_description', 'email',
                      'social_caption', 'faq_answer')),
    topic         text not null,
    tone          text,
    body          text not null,
    status        text not null default 'draft'
                    check (status in ('draft', 'approved')),
    -- Whether matching documents were found to ground the draft.
    grounded      boolean not null default false,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create index if not exists content_drafts_user_id_idx
    on public.content_drafts (user_id);
create index if not exists content_drafts_agent_id_idx
    on public.content_drafts (agent_id);

-- RLS on: the backend uses the service-role key (bypasses RLS), so no client
-- can read these with the anon key. Matches the other tables.
alter table public.leads enable row level security;
alter table public.content_drafts enable row level security;

-- Keep updated_at fresh on writes.
create or replace function public.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists leads_set_updated_at on public.leads;
create trigger leads_set_updated_at
    before update on public.leads
    for each row execute function public.set_updated_at();

drop trigger if exists content_drafts_set_updated_at on public.content_drafts;
create trigger content_drafts_set_updated_at
    before update on public.content_drafts
    for each row execute function public.set_updated_at();
