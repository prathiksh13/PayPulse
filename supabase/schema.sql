-- PayPulse - Supabase Auth schema (profiles + merchants) and RLS policies.
-- Run this once in the Supabase SQL Editor.
--
-- NOTE: The operational tables (payments, anomalies, recovery, checkout,
-- mandates, ai_decisions, audit_log, daily_reports, etc.) are created by the
-- FastAPI app via SQLAlchemy on startup against the DATABASE_URL. If you point
-- DATABASE_URL at your Supabase Postgres, those tables are created there too.
-- This file covers ONLY the Supabase-managed auth tables used for RBAC.

-- ---------------------------------------------------------------------------
-- Auth trigger: auto-create a profile row when a new user signs up.
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, name, role, merchant_id, is_active)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'full_name', new.email),
    'analyst',                                   -- default role; promote admins manually or via profile update
    'demo_merchant_001',                         -- shared demo merchant
    true
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ---------------------------------------------------------------------------
-- profiles
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  email       text,
  name        text,
  role        text not null default 'analyst' check (role in ('admin', 'analyst')),
  merchant_id text,
  is_active   boolean not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

alter table public.profiles enable row level security;

-- Users can read their own profile.
create policy "profiles_select_own"
  on public.profiles for select
  using (auth.uid() = id);

-- Users can update some fields of their own profile.
create policy "profiles_update_own"
  on public.profiles for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Service role (server) can manage all profiles. The app talks to this table
-- using the service-role key, which bypasses RLS by default. The policies above
-- are for completeness / frontend use only.

-- ---------------------------------------------------------------------------
-- merchants
-- ---------------------------------------------------------------------------
create table if not exists public.merchants (
  id          text primary key,
  name        text,
  environment text not null default 'test',
  is_demo     boolean not null default false,
  created_at  timestamptz not null default now()
);

alter table public.merchants enable row level security;

-- Any authenticated user can read merchants (needed to resolve merchant info).
create policy "merchants_select_auth"
  on public.merchants for select
  using (auth.role() = 'authenticated');

-- ---------------------------------------------------------------------------
-- Seed the demo merchant (idempotent).
-- ---------------------------------------------------------------------------
insert into public.merchants (id, name, environment, is_demo)
values ('demo_merchant_001', 'PayPulse Demo Merchant', 'test', true)
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- NOTE on demo users:
-- Create the two demo users in Authentication > Users (or via the API):
--   admin@paypulse.demo   /  PayPulse@123   (then set role='admin' in profiles)
--   analyst@paypulse.demo /  PayPulse@123   (role stays 'analyst')
-- After creating them, if you used the UI (not the trigger path), run:
--   update public.profiles set role='admin' where email='admin@paypulse.demo';
-- ---------------------------------------------------------------------------
