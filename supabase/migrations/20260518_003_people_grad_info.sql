-- =====================================================================
-- Marist Time Machine — canonical graduation info on people
-- Until now, the year/class shown for a person was derived from the
-- photos where they appear (a salad, since people show up in events of
-- multiple classes). Now we let admin/community settle the canonical
-- truth, with the derived list as fallback when unset.
-- =====================================================================

alter table public.people
  add column if not exists graduation_year int
    check (graduation_year is null or graduation_year between 1900 and 2100),
  add column if not exists class_letter text
    check (class_letter is null or class_letter ~ '^[A-F]$');

create index if not exists people_grad_idx
  on public.people(graduation_year, class_letter);

-- Suggestions now carry an optional year/class proposal too.
alter table public.name_suggestions
  add column if not exists suggested_graduation_year int
    check (suggested_graduation_year is null
           or suggested_graduation_year between 1900 and 2100),
  add column if not exists suggested_class_letter text
    check (suggested_class_letter is null
           or suggested_class_letter ~ '^[A-F]$');
