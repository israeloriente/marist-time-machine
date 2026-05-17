# Marist Time Machine

PWA de "máquina do tempo" do acervo Marista: o usuário tira uma selfie e o
sistema retorna **todas as fotos do acervo onde aquela pessoa aparece**.

A arquitetura replica internamente o pipeline do [Immich](https://immich.app)
para reconhecimento facial, sem usar o Immich como dependência.

## Stack

| Camada | Tecnologia | Por quê |
|---|---|---|
| Frontend | Vue 3 + Vite + vite-plugin-pwa | Sem app nativo; instalável via PWA |
| Backend (negócio) | FastAPI (`api/`) | Valida JWT do Supabase, orquestra ingestão/busca |
| Backend (ML) | FastAPI (`ml/`) + InsightFace buffalo_l | SCRFD + ArcFace 512-D em ONNX Runtime |
| Banco | Postgres 17 + **pgvector** (HNSW, cosine) | Mesmo banco para metadados, auth e vetores |
| Auth + Storage | Supabase self-hosted | Substitui MongoDB + MinIO |
| Orquestração | Docker Compose | Deploy em Coolify usa o mesmo `docker-compose.yml` |

Modelo facial idêntico ao Immich:
**SCRFD-10G-KPS** (detecção) → alinhamento 5-pt → **ArcFace ResNet50**
(embedding 512-D L2-normalizado) → busca cosine via operador `<=>` do
pgvector → clustering DBSCAN-streaming.

## Estrutura

```
.
├── docker-compose.yml           # Stack completo (Supabase + api + ml + web)
├── docker-compose.override.yml  # Dev local (expõe portas, hot-reload)
├── .env.example                 # Variáveis de ambiente
├── supabase/
│   ├── init/                    # Extensões aplicadas no boot do Postgres
│   ├── migrations/              # Schema + RLS + buckets
│   └── kong/kong.yml            # Roteamento do API gateway
├── api/                         # FastAPI principal
├── ml/                          # Serviço InsightFace
└── web/                         # Vue 3 + Vite + PWA
```

## Pré-requisitos

- Docker 24+ e Docker Compose v2
- ~4 GB de RAM livres (primeiro download do buffalo_l são ~250 MB)
- Para desenvolvimento local do frontend: Node 20+

## Bootstrap local

### 1. Variáveis de ambiente

```bash
cp .env.example .env
```

Gere `JWT_SECRET` forte:

```bash
openssl rand -base64 64 | tr -d '\n' | head -c 64
```

Gere `ANON_KEY` e `SERVICE_ROLE_KEY` (JWTs assinados com `JWT_SECRET`):

```bash
docker run --rm --network=host -e JWT_SECRET="$(grep JWT_SECRET .env | cut -d= -f2)" \
  node:20-alpine sh -c 'npm i -g jsonwebtoken-cli >/dev/null 2>&1; \
    jwt sign --secret $JWT_SECRET '"'"'{"role":"anon","iss":"supabase","iat":1700000000,"exp":2000000000}'"'"'; \
    echo; \
    jwt sign --secret $JWT_SECRET '"'"'{"role":"service_role","iss":"supabase","iat":1700000000,"exp":2000000000}'"'"'; '
```

Cole os dois JWTs em `ANON_KEY` e `SERVICE_ROLE_KEY`. Use o `ANON_KEY`
também em `VITE_SUPABASE_ANON_KEY`.

### 2. Subir tudo

```bash
docker compose up -d --build
```

Primeira execução demora ~5 min (build das imagens + download do InsightFace).

Endpoints locais:

- Web (PWA): http://localhost:5173
- API negócio: http://localhost:8080/docs
- ML service: http://localhost:8081/docs
- Supabase Studio: http://localhost:3001 (login `DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`)
- Kong gateway: http://localhost:8000

### 3. Criar usuário

Abra http://localhost:5173, clique em **Criar conta**. Como
`GOTRUE_MAILER_AUTOCONFIRM=true` em dev, o login é imediato.

### 4. Ingerir fotos do acervo

Use `POST /photos` da API (form-data: `file` + `metadata_json`) ou um
script no diretório `scripts/` (a ser adicionado). A primeira foto
dispara o download dos pesos InsightFace.

### 5. Buscar

No PWA, **Buscar** → permita câmera → **Buscar**. O resultado mostra
todas as fotos onde a pessoa identificada aparece.

## Deploy em Coolify (automatizado via API)

Use o script `scripts/coolify-deploy.sh`. Fluxo:

### 1. Pré-requisitos no Coolify (uma vez)

a. **Gerar API token** → Avatar → Keys & Tokens → Create token (read+write+deploy)

b. **Subir Supabase via template** (Coolify > Resources > One-click > Supabase).
   Anote da página do resource:
   - URL interna do Kong (algo como `http://supabase-kong-<id>:8000`)
   - URL pública (FQDN configurado)
   - ANON_KEY, SERVICE_ROLE_KEY, JWT_SECRET
   - `DATABASE_URL` (use `postgres://postgres:<password>@<supabase-db-host>:5432/postgres`)

### 2. Push do repo pra GitHub (público)

```bash
git remote add origin https://github.com/<seu-user>/<seu-repo>.git
git add -A && git commit -m "marist time machine: initial commit"
git push -u origin main
```

> Repo precisa ser público — a API do Coolify não tem endpoint
> pra configurar GitHub App privado; pode tornar privado depois.

### 3. Configurar variáveis

```bash
cp scripts/.coolify.env.example scripts/.coolify.env
$EDITOR scripts/.coolify.env       # preencher tudo
```

### 4. Rodar deploy

```bash
./scripts/coolify-deploy.sh
```

O script:
1. Cria o projeto `marist-time-machine` (se não existir)
2. Cria a application apontando pro repo + branch
3. Define todas as env vars
4. Dispara o deploy

Acompanhe o build/logs pela UI do Coolify (URL impressa no fim do script).

## Deploy em Coolify (manual)

1. Criar uma aplicação **Docker Compose** no Coolify apontando para este repo.
2. **Não** subir `docker-compose.override.yml` (Coolify usa só
   `docker-compose.yml` automaticamente).
3. Configurar as variáveis de ambiente do `.env.example` na UI do Coolify.
   - `SITE_URL`, `API_EXTERNAL_URL`, `SUPABASE_PUBLIC_URL`,
     `VITE_SUPABASE_URL`, `VITE_API_URL` devem usar os domínios públicos
     que o Coolify expor.
   - `GOTRUE_URI_ALLOW_LIST` deve incluir o domínio do PWA.
4. Coolify cuida do Traefik/TLS automaticamente. Apontar cada serviço
   exposto (`web`, `api`, `kong`) para um FQDN diferente.
5. Volumes nomeados (`db-data`, `storage-data`, `ml-models`) persistem
   automaticamente entre deploys.

## Storage: `file` (dev) vs `s3` / Hetzner Object Storage (prod)

O Supabase Storage suporta dois backends, controlados por `STORAGE_BACKEND`:

| Modo | Quando usar | Onde os bytes ficam |
|---|---|---|
| `file` (default) | dev local | volume Docker `storage-data` |
| `s3` | produção | Hetzner Object Storage (ou qualquer bucket S3-compatible) |

A aplicação **não muda em nada** entre os dois — `signed URLs`, RLS,
upload, image transforms continuam idênticos. Só os bytes mudam de lugar.

### Configurar Hetzner Object Storage

1. **Console Hetzner Cloud** → Object Storage → **Create Bucket**
   - Região: a mesma da VPS (`fsn1`, `nbg1`, `hel1`, `ash`)
   - Nome: ex. `marist-time-machine`
   - Visibility: **private**
2. **Credentials** → Generate Access Key + Secret Key
3. No `.env` (ou no Coolify), defina:
   ```bash
   STORAGE_BACKEND=s3
   S3_BUCKET=marist-time-machine
   S3_ENDPOINT=https://fsn1.your-objectstorage.com
   S3_REGION=fsn1
   S3_ACCESS_KEY=...
   S3_SECRET_KEY=...
   IMGPROXY_USE_S3=true
   ```
4. Restart: `docker compose up -d storage imgproxy`

> Tanto a VPS quanto o bucket devem estar na **mesma região Hetzner** —
> assim o tráfego é interno e gratuito.

## Tunáveis

| Variável | Default | O quê |
|---|---|---|
| `ML_MODEL_NAME` | `buffalo_l` | `buffalo_s/m/l` ou `antelopev2` (mais pesado, mais preciso) |
| `ML_DET_THRESHOLD` | `0.7` | Mínimo confidence para considerar detecção |
| `CLUSTER_MAX_DISTANCE` | `0.5` | Distância cosine máxima entre rostos da mesma pessoa |
| `CLUSTER_MIN_FACES` | `3` | Mínimo de vizinhos para criar nova pessoa |

## Roadmap curto

- [ ] Worker assíncrono para re-processar lote noturno (estilo Immich)
- [ ] Endpoint `/people/{id}/merge` na UI (admin)
- [ ] Thumbnail pipeline via `imgproxy`
- [ ] GPU opcional (CUDAExecutionProvider) por env var
- [ ] Re-clustering global periódico

## Notas

- **Sem mock de banco**: integramos direto com Postgres real via asyncpg.
- **JWT HS256**: validado localmente no FastAPI; nada de chamada externa por request.
- **Storage**: Supabase Storage usa filesystem (volume `storage-data`).
  Em produção com alto volume, considerar S3 backend (`STORAGE_BACKEND=s3`).
- **Coolify**: o `docker-compose.yml` é deliberadamente parametrizado por
  env vars e não fixa portas nem domínios — Coolify injeta tudo via UI.
