-- =====================================================================
-- Marist Time Machine — songs moderation
-- Every added song must be approved by admin before showing up in the
-- public mural and the kiosk soundtrack.
-- =====================================================================

alter table public.songs
  add column if not exists moderation_status text
    not null default 'pending'
    check (moderation_status in ('pending', 'approved', 'rejected')),
  add column if not exists moderation_note text,
  add column if not exists moderated_at timestamptz,
  add column if not exists moderated_by uuid references auth.users(id) on delete set null;

create index if not exists songs_moderation_status_idx
  on public.songs(moderation_status);

-- Grandfather anything already in the DB before this migration to approved.
update public.songs
   set moderation_status = 'approved',
       moderated_at = coalesce(moderated_at, now())
 where moderation_status = 'pending'
   and created_at < now() - interval '1 minute';
