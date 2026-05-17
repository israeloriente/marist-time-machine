-- =====================================================================
-- Row-Level Security policies
-- App reads/writes go through the FastAPI service using the service_role
-- key, which bypasses RLS. RLS here protects direct Data-API access by
-- authenticated end-users (via Supabase JS) so they can only read.
-- =====================================================================

alter table public.photos  enable row level security;
alter table public.people  enable row level security;
alter table public.faces   enable row level security;

-- Authenticated users can read everything (browsing the archive).
drop policy if exists "photos_select_authenticated" on public.photos;
create policy "photos_select_authenticated"
  on public.photos for select
  to authenticated
  using (true);

drop policy if exists "people_select_authenticated" on public.people;
create policy "people_select_authenticated"
  on public.people for select
  to authenticated
  using (is_hidden = false);

drop policy if exists "faces_select_authenticated" on public.faces;
create policy "faces_select_authenticated"
  on public.faces for select
  to authenticated
  using (true);

-- No INSERT/UPDATE/DELETE policies for the public roles — all writes go
-- through the FastAPI service using the service_role key.

-- Expose tables to the Data API (Supabase 2026-04 change: tables are no
-- longer auto-exposed, so we GRANT explicitly).
grant usage on schema public to anon, authenticated;
grant select on public.photos, public.people, public.faces to authenticated;
