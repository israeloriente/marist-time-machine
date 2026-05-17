-- =====================================================================
-- Marist Time Machine — initial schema
-- Mirrors Immich's face-recognition data model.
-- =====================================================================

-- Photos: rows for each image ingested into the archive
create table if not exists public.photos (
  id uuid primary key default gen_random_uuid(),
  storage_bucket text not null default 'photos',
  storage_path text not null,
  original_filename text,
  uploaded_by uuid references auth.users(id) on delete set null,
  uploaded_at timestamptz not null default now(),
  width int,
  height int,
  metadata jsonb not null default '{}'::jsonb,
  processed_at timestamptz,
  processing_error text
);

create index if not exists photos_uploaded_by_idx on public.photos(uploaded_by);
create index if not exists photos_uploaded_at_idx on public.photos(uploaded_at desc);
create index if not exists photos_processed_at_idx on public.photos(processed_at);

-- People: clusters of faces representing the same person
create table if not exists public.people (
  id uuid primary key default gen_random_uuid(),
  display_name text,
  thumbnail_face_id uuid,
  is_hidden boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists people_display_name_idx on public.people(display_name);

-- Faces: detected face with embedding (one row per face per photo)
create table if not exists public.faces (
  id uuid primary key default gen_random_uuid(),
  photo_id uuid not null references public.photos(id) on delete cascade,
  person_id uuid references public.people(id) on delete set null,
  bbox jsonb not null,
  landmarks jsonb,
  detection_score real,
  embedding vector(512) not null,
  created_at timestamptz not null default now()
);

create index if not exists faces_photo_idx on public.faces(photo_id);
create index if not exists faces_person_idx on public.faces(person_id);

-- HNSW index for fast cosine similarity search (Immich-style).
-- m=16, ef_construction=64 are sensible defaults; tune later.
create index if not exists faces_embedding_hnsw_idx
  on public.faces
  using hnsw (embedding vector_cosine_ops)
  with (m = 16, ef_construction = 64);

-- Back-reference: people.thumbnail_face_id -> faces.id (added after faces exists)
alter table public.people
  drop constraint if exists people_thumbnail_face_fk;
alter table public.people
  add constraint people_thumbnail_face_fk
  foreign key (thumbnail_face_id) references public.faces(id) on delete set null;

-- updated_at trigger
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists people_updated_at on public.people;
create trigger people_updated_at
  before update on public.people
  for each row execute function public.set_updated_at();
