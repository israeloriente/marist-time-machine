-- =====================================================================
-- Marist Time Machine — people.status
-- Replaces the one-way is_hidden flag with a reversible status field.
-- A rejected person disappears from admin lists, search results and the
-- contribute flow, but can be reactivated.
-- =====================================================================

alter table public.people
  add column if not exists status text
    not null default 'active'
    check (status in ('active', 'rejected'));

-- Backfill: previously-hidden people land in the rejected bucket.
update public.people
   set status = 'rejected'
 where is_hidden = true
   and status = 'active';

create index if not exists people_status_idx
  on public.people(status);

-- Keep is_hidden in sync so anything we missed (RLS policies, ad-hoc
-- queries) keeps behaving. Newly-set status drives the column going
-- forward; we'll drop is_hidden once we're sure nothing depends on it.
create or replace function public.people_sync_hidden_from_status()
returns trigger language plpgsql as $$
begin
  new.is_hidden := (new.status = 'rejected');
  return new;
end;
$$;

drop trigger if exists people_sync_hidden_from_status on public.people;
create trigger people_sync_hidden_from_status
  before insert or update of status on public.people
  for each row execute function public.people_sync_hidden_from_status();
