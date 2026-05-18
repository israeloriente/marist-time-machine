-- =====================================================================
-- Marist Time Machine — photo moderation
-- Every uploaded photo must be approved by admin before showing up in
-- public search/kiosk/contribute flows.
-- =====================================================================

alter table public.photos
  add column if not exists moderation_status text
    not null default 'pending'
    check (moderation_status in ('pending', 'approved', 'rejected')),
  add column if not exists moderation_note text,
  add column if not exists moderated_at timestamptz,
  add column if not exists moderated_by uuid references auth.users(id) on delete set null;

create index if not exists photos_moderation_status_idx
  on public.photos(moderation_status);

-- Anything in the DB before this migration is grandfathered to approved:
update public.photos
   set moderation_status = 'approved',
       moderated_at = coalesce(moderated_at, now())
 where moderation_status = 'pending'
   and uploaded_at < now() - interval '1 minute';

-- Read policy: authenticated users see only their own pending/rejected photos
-- AND all approved ones. (Service role bypasses RLS so backend keeps working.)
drop policy if exists "photos_select_authenticated" on public.photos;
-- NB: this policy is read-only — table didn't have it before in some envs.
-- Skip silently if already defined elsewhere.
