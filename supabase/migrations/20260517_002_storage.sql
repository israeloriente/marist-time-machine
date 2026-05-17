-- =====================================================================
-- Storage buckets and policies
-- =====================================================================

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('photos',     'photos',     false, 52428800, array['image/jpeg','image/png','image/webp','image/heic']),
  ('thumbnails', 'thumbnails', true,   5242880, array['image/jpeg','image/webp'])
on conflict (id) do nothing;

-- Authenticated users can read photos via signed URLs issued by the API.
-- Thumbnails are public.
drop policy if exists "thumbnails_public_read" on storage.objects;
create policy "thumbnails_public_read"
  on storage.objects for select
  to anon, authenticated
  using (bucket_id = 'thumbnails');

drop policy if exists "photos_authenticated_read" on storage.objects;
create policy "photos_authenticated_read"
  on storage.objects for select
  to authenticated
  using (bucket_id = 'photos');
