-- Persistent YouTube OAuth connections for Socialized.
-- OAuth tokens are encrypted by the app before insertion.
create table if not exists public.youtube_connections (
  channel_id text primary key,
  channel_title text not null,
  custom_url text,
  thumbnail text,
  token_json text not null,
  updated_at timestamptz not null default now()
);

alter table public.youtube_connections enable row level security;

-- The Streamlit backend uses the Supabase service-role key server-side.
-- Do not expose this table to browser/anon clients.
revoke all on table public.youtube_connections from anon, authenticated;
grant all on table public.youtube_connections to service_role;

create index if not exists youtube_connections_updated_at_idx
  on public.youtube_connections (updated_at desc);
