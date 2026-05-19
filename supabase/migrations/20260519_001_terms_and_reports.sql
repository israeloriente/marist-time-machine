-- =====================================================================
-- Marist Time Machine — política de privacidade + sistema de denúncia
-- =====================================================================

-- ---- 1) Termos de uso ---------------------------------------------------
-- Quando o usuário aceita a política, gravamos a data e a versão do texto
-- aceito (pra que a gente possa pedir re-aceitação se a política mudar).
alter table public.user_profiles
  add column if not exists terms_accepted_at timestamptz,
  add column if not exists terms_version text;

create index if not exists user_profiles_terms_idx
  on public.user_profiles(terms_accepted_at);


-- ---- 2) Tabela de denúncias --------------------------------------------
-- Uma denúncia aponta para uma foto (ou um rosto específico dentro da foto)
-- e fica pendente até um admin resolver. Mantemos histórico mesmo após
-- resolução para auditoria.
create table if not exists public.reports (
  id              uuid primary key default gen_random_uuid(),
  -- Quem denunciou
  reporter_id     uuid not null references auth.users(id) on delete set null,
  reporter_email  text,                            -- snapshot, caso a conta suma
  -- O que está sendo denunciado
  photo_id        uuid references public.photos(id) on delete cascade,
  face_id         uuid references public.faces(id) on delete cascade,
  -- Por quê
  reason          text not null check (char_length(reason) between 1 and 2000),
  contact_info    text,                            -- opcional: pra o admin retornar
  -- Status
  status          text not null default 'pending'
                  check (status in ('pending', 'resolved_removed', 'resolved_rejected')),
  resolution_note text,
  resolved_at     timestamptz,
  resolved_by     uuid references auth.users(id) on delete set null,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  -- Pelo menos um alvo precisa estar definido
  constraint reports_has_target check (photo_id is not null or face_id is not null)
);

create index if not exists reports_status_idx   on public.reports(status);
create index if not exists reports_photo_idx    on public.reports(photo_id);
create index if not exists reports_reporter_idx on public.reports(reporter_id);
create index if not exists reports_created_idx  on public.reports(created_at desc);

drop trigger if exists reports_updated_at on public.reports;
create trigger reports_updated_at
  before update on public.reports
  for each row execute function public.set_updated_at();


-- ---- 3) RLS pro reports -------------------------------------------------
-- Usuário autenticado pode criar denúncias e ver as próprias.
-- Admin (via service_role no backend) gerencia tudo.
alter table public.reports enable row level security;

drop policy if exists "reports_insert_own" on public.reports;
create policy "reports_insert_own"
  on public.reports for insert to authenticated
  with check (reporter_id = auth.uid());

drop policy if exists "reports_select_own" on public.reports;
create policy "reports_select_own"
  on public.reports for select to authenticated
  using (reporter_id = auth.uid());

grant select, insert on public.reports to authenticated;
