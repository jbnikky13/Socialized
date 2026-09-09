alter table public.youtube_connections add column if not exists connection_key text;
create index if not exists youtube_connections_connection_key_idx on public.youtube_connections(connection_key);
