-- =====================================================================
-- Marist Time Machine — crowd-sourced name suggestions
-- Users propose names for people / orphan faces.
-- Admins approve them (which sets display_name) or reject.
-- =====================================================================

create table if not exists public.name_suggestions (
  id uuid primary key default gen_random_uuid(),
  person_id uuid references public.people(id) on delete cascade,
  face_id   uuid references public.faces(id)  on delete cascade,
  suggested_name   text not null,
  normalized_name  text not null,
  suggested_by     uuid references auth.users(id) on delete set null,
  status           text not null default 'pending'
                   check (status in ('pending','approved','rejected')),
  created_at       timestamptz not null default now(),
  resolved_at      timestamptz,
  resolved_by      uuid references auth.users(id) on delete set null,

  -- A suggestion must target either a person OR a face, not both, not neither.
  constraint suggestion_has_target check (
    (person_id is not null and face_id is null) or
    (person_id is null and face_id is not null)
  )
);

create index if not exists name_sugg_person_idx     on public.name_suggestions(person_id) where person_id is not null;
create index if not exists name_sugg_face_idx       on public.name_suggestions(face_id)   where face_id   is not null;
create index if not exists name_sugg_status_idx     on public.name_suggestions(status);
create index if not exists name_sugg_norm_idx       on public.name_suggestions(normalized_name);

-- Prevent the same user from voting twice on the same target with the same name.
create unique index if not exists name_sugg_dedupe_idx
  on public.name_suggestions(coalesce(person_id::text, face_id::text), normalized_name, suggested_by)
  where status = 'pending';

-- RLS
alter table public.name_suggestions enable row level security;

drop policy if exists "suggestions_select_authenticated" on public.name_suggestions;
create policy "suggestions_select_authenticated"
  on public.name_suggestions for select
  to authenticated
  using (true);

-- INSERT/UPDATE/DELETE go through the FastAPI service-role; no policies for
-- end users to write directly via the Data API.

grant select on public.name_suggestions to authenticated;
