-- One-time setup for free-tier Supabase keep-alive (GitHub Actions).
-- Run in Supabase → SQL Editor if you have not already.

create table if not exists public.keepalive (
  id int primary key default 1,
  last_ping timestamptz default now()
);

insert into public.keepalive (id) values (1)
on conflict (id) do nothing;

-- Service role / secret key used by the Action bypasses RLS.
-- No extra policies required for that key.
