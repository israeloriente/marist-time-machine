-- =====================================================================
-- Marist Time Machine — songs that marked each user's life at Marista.
-- One row per (user, video). UI groups by user's class+year for "trilha
-- sonora da turma".
-- =====================================================================

create table if not exists public.songs (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  youtube_id      text not null,
  title           text,
  channel         text,
  caption         text,            -- user's personal note ("dança da formatura")
  thumbnail_url   text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

-- Same user can't add the same video twice
create unique index if not exists songs_user_video_idx
  on public.songs(user_id, youtube_id);

-- Fast feed by user / by recent
create index if not exists songs_user_idx       on public.songs(user_id);
create index if not exists songs_created_idx    on public.songs(created_at desc);

drop trigger if exists songs_updated_at on public.songs;
create trigger songs_updated_at
  before update on public.songs
  for each row execute function public.set_updated_at();

-- =====================================================================
-- RLS
-- - All authenticated users can read all songs (public mural).
-- - Each user can insert/update/delete only their own songs.
-- =====================================================================
alter table public.songs enable row level security;

drop policy if exists "songs_select_authenticated" on public.songs;
create policy "songs_select_authenticated"
  on public.songs for select to authenticated using (true);

drop policy if exists "songs_insert_own" on public.songs;
create policy "songs_insert_own"
  on public.songs for insert to authenticated with check (user_id = auth.uid());

drop policy if exists "songs_update_own" on public.songs;
create policy "songs_update_own"
  on public.songs for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists "songs_delete_own" on public.songs;
create policy "songs_delete_own"
  on public.songs for delete to authenticated using (user_id = auth.uid());

grant select, insert, update, delete on public.songs to authenticated;
