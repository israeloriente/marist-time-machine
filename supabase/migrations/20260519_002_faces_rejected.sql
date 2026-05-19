-- =====================================================================
-- Marist Time Machine — face rejection
-- Admin pode marcar rostos como rejeitados (não-pessoa, captura ruim,
-- objeto que virou rosto, etc). O rosto NÃO é apagado — fica auditável
-- e a ação é reversível — mas some das filas e do reconhecimento.
-- =====================================================================

alter table public.faces
  add column if not exists is_rejected boolean not null default false,
  add column if not exists rejected_at timestamptz,
  add column if not exists rejected_by uuid references auth.users(id) on delete set null;

create index if not exists faces_is_rejected_idx
  on public.faces(is_rejected)
  where is_rejected = false;
