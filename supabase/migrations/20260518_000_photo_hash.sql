-- =====================================================================
-- Marist Time Machine — content_hash for deduplication
-- =====================================================================

alter table public.photos
  add column if not exists content_hash text;

create index if not exists photos_content_hash_idx
  on public.photos(content_hash);

-- Unique constraint allows multiple null hashes (for legacy rows pre-backfill)
-- but blocks duplicates once populated.
create unique index if not exists photos_content_hash_unique
  on public.photos(content_hash)
  where content_hash is not null;
