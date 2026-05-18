-- =====================================================================
-- Marist Time Machine — user profiles
-- One row per authenticated user with their Marista graduation info.
-- Onboarding flow forces users to fill this in right after signup.
-- =====================================================================

create table if not exists public.user_profiles (
  user_id          uuid primary key references auth.users(id) on delete cascade,
  graduation_year  int  not null check (graduation_year between 1900 and 2100),
  class_letter     text not null check (class_letter ~ '^[A-F]$'),
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index if not exists user_profiles_grad_idx
  on public.user_profiles(graduation_year, class_letter);

-- updated_at trigger
drop trigger if exists user_profiles_updated_at on public.user_profiles;
create trigger user_profiles_updated_at
  before update on public.user_profiles
  for each row execute function public.set_updated_at();

-- =====================================================================
-- RLS: user can read/write *only* their own profile
-- =====================================================================
alter table public.user_profiles enable row level security;

drop policy if exists "user_profile_select_own" on public.user_profiles;
create policy "user_profile_select_own"
  on public.user_profiles for select
  to authenticated
  using (user_id = auth.uid());

drop policy if exists "user_profile_insert_own" on public.user_profiles;
create policy "user_profile_insert_own"
  on public.user_profiles for insert
  to authenticated
  with check (user_id = auth.uid());

drop policy if exists "user_profile_update_own" on public.user_profiles;
create policy "user_profile_update_own"
  on public.user_profiles for update
  to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

grant usage on schema public to authenticated;
grant select, insert, update on public.user_profiles to authenticated;
