create table if not exists public.youtube_connections (
  id uuid primary key default gen_random_uuid(),
  google_account_id text,
  google_email text,
  channel_id text not null,
  channel_title text not null,
  channel_thumbnail_url text,
  token_json text not null,
  active boolean default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.youtube_connections add column if not exists google_account_id text;
alter table public.youtube_connections add column if not exists google_email text;
alter table public.youtube_connections add column if not exists channel_id text;
alter table public.youtube_connections add column if not exists channel_title text;
alter table public.youtube_connections add column if not exists channel_thumbnail_url text;
alter table public.youtube_connections add column if not exists token_json text;
alter table public.youtube_connections add column if not exists active boolean default false;
alter table public.youtube_connections add column if not exists created_at timestamptz default now();
alter table public.youtube_connections add column if not exists updated_at timestamptz default now();

create unique index if not exists youtube_connections_channel_id_uidx on public.youtube_connections(channel_id);
create index if not exists youtube_connections_google_email_idx on public.youtube_connections(google_email);

alter table public.youtube_connections enable row level security;
