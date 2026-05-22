-- =====================================================================
-- Marist Time Machine — collaborators vs students on people
-- People can now be either a 'student' (graduation_year + class_letter)
-- or a 'collaborator' (a teacher/staff member with an entry_year..exit_year
-- range instead of a single graduation year). person_type defaults to
-- 'student' so all existing rows stay valid and unchanged.
--
-- Name suggestions carry the proposed type + range too, so the crowd-
-- sourcing pipeline (suggest -> approve) can settle this just like it
-- already settles name/year/class.
-- =====================================================================

alter table public.people
  add column if not exists person_type text not null default 'student'
    check (person_type in ('student', 'collaborator')),
  add column if not exists entry_year int
    check (entry_year is null or entry_year between 1900 and 2100),
  add column if not exists exit_year int
    check (exit_year is null or exit_year between 1900 and 2100);

-- No index on (entry_year, exit_year): the kiosk year-range queries reach
-- people via faces.person_id (already indexed) and the people PK, never by a
-- standalone year-range scan, so such an index would never be used.

alter table public.name_suggestions
  add column if not exists suggested_person_type text
    check (suggested_person_type is null
           or suggested_person_type in ('student', 'collaborator')),
  add column if not exists suggested_entry_year int
    check (suggested_entry_year is null
           or suggested_entry_year between 1900 and 2100),
  add column if not exists suggested_exit_year int
    check (suggested_exit_year is null
           or suggested_exit_year between 1900 and 2100);
