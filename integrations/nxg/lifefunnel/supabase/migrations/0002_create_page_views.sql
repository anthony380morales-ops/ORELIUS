-- NXG Life Group — page_views table (lightweight, privacy-preserving traffic log).
--
-- Powers ORELIUS's daily "how many people and devices visited" briefing without
-- any paid analytics add-on. Rows are written ONLY by the server-side Netlify
-- function `track-view` using the Supabase service role (bypasses RLS), so no
-- write access is exposed to the browser. No raw IP or user-agent is stored — a
-- per-day, per-person hash is the only visitor identifier, so "people" = distinct
-- hashes and no personal data is retained.
--
-- Apply in the SAME Supabase project as the leads table
-- (Project → SQL Editor → paste → Run), or via `supabase db push`.

create extension if not exists pgcrypto;

create table if not exists public.page_views (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  path text,                 -- e.g. "/", "/quiz", "/results"
  device text,               -- mobile | tablet | desktop | bot | unknown
  visitor_hash text,         -- daily per-person hash (no raw IP/UA kept)
  referrer text
);

create index if not exists page_views_created_at_idx on public.page_views (created_at desc);
create index if not exists page_views_visitor_hash_idx on public.page_views (visitor_hash);

alter table public.page_views enable row level security;

-- The dashboard (authenticated) and service role may read; nobody may write from
-- the browser. The Netlify function writes with the service role, which bypasses
-- RLS entirely, so no insert policy is granted here on purpose.
create policy "authenticated can read page_views"
  on public.page_views for select to authenticated using (true);
