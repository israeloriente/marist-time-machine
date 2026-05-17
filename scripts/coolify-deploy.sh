#!/usr/bin/env bash
# =====================================================================
# Marist Time Machine — deploy via Coolify API
#
# Prereqs (all set as env vars or in scripts/.coolify.env):
#   COOLIFY_URL                e.g. http://localhost:8000
#   COOLIFY_TOKEN              API token (Bearer)
#   COOLIFY_SERVER_UUID        from GET /api/v1/servers
#   COOLIFY_PROJECT_NAME       e.g. marist-time-machine (created if missing)
#   COOLIFY_ENVIRONMENT_NAME   e.g. production
#   GIT_REPO                   https://github.com/<you>/<repo>.git (public)
#   GIT_BRANCH                 e.g. main
#
# Supabase vars (from Supabase resource you created in Coolify):
#   SUPABASE_URL               internal Kong URL (e.g. http://supabase-kong-xxx:8000)
#   SUPABASE_PUBLIC_URL        public URL of the Supabase resource
#   ANON_KEY
#   SERVICE_ROLE_KEY
#   JWT_SECRET
#   DATABASE_URL               postgres://postgres:<pw>@<supabase-db>:5432/postgres
#
# App-specific:
#   SERVICE_FQDN_WEB           e.g. app.marist.example.com
#   SERVICE_FQDN_API           e.g. api.marist.example.com
# =====================================================================

set -euo pipefail

ENV_FILE="${SCRIPT_DIR:-$(cd "$(dirname "$0")" && pwd)}/.coolify.env"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi

: "${COOLIFY_URL:?missing COOLIFY_URL}"
: "${COOLIFY_TOKEN:?missing COOLIFY_TOKEN}"
: "${COOLIFY_SERVER_UUID:?missing COOLIFY_SERVER_UUID}"
: "${COOLIFY_PROJECT_NAME:=marist-time-machine}"
: "${COOLIFY_ENVIRONMENT_NAME:=production}"
: "${GIT_REPO:?missing GIT_REPO (public HTTPS URL)}"
: "${GIT_BRANCH:=main}"

H_AUTH=(-H "Authorization: Bearer $COOLIFY_TOKEN" -H "Content-Type: application/json")

# ---------- helpers ----------
api() {
  local method=$1 path=$2 body=${3:-}
  if [[ -n "$body" ]]; then
    curl -sS -X "$method" "${H_AUTH[@]}" --data "$body" "$COOLIFY_URL$path"
  else
    curl -sS -X "$method" "${H_AUTH[@]}" "$COOLIFY_URL$path"
  fi
}

jq_get() { python3 -c "import sys,json; print(json.load(sys.stdin).get('$1',''))"; }

# ---------- 1. ensure project ----------
echo ">> Ensuring project '$COOLIFY_PROJECT_NAME' exists..."
PROJECT_UUID=$(api GET /api/v1/projects | python3 -c "
import sys,json
projects=json.load(sys.stdin)
for p in projects:
    if p.get('name')=='${COOLIFY_PROJECT_NAME}':
        print(p['uuid']); break
")
if [[ -z "$PROJECT_UUID" ]]; then
  echo "   creating project..."
  PROJECT_UUID=$(api POST /api/v1/projects \
    "$(printf '{"name":"%s","description":"Marist Time Machine"}' "$COOLIFY_PROJECT_NAME")" \
    | jq_get uuid)
fi
echo "   project_uuid=$PROJECT_UUID"

# ---------- 2. ensure application ----------
APP_NAME="marist-app"
echo ">> Ensuring application '$APP_NAME' exists..."

# look up existing app by name within project
APP_UUID=$(api GET "/api/v1/applications" | python3 -c "
import sys,json
apps=json.load(sys.stdin)
for a in apps:
    if a.get('name')=='${APP_NAME}' and a.get('project',{}).get('uuid')=='${PROJECT_UUID}':
        print(a['uuid']); break
" 2>/dev/null || true)

if [[ -z "$APP_UUID" ]]; then
  echo "   creating application..."
  PAYLOAD=$(python3 - <<PY
import json
print(json.dumps({
  "project_uuid": "$PROJECT_UUID",
  "server_uuid":  "$COOLIFY_SERVER_UUID",
  "environment_name": "$COOLIFY_ENVIRONMENT_NAME",
  "git_repository": "$GIT_REPO",
  "git_branch": "$GIT_BRANCH",
  "build_pack": "dockercompose",
  "docker_compose_location": "docker-compose.coolify.yml",
  "name": "$APP_NAME",
  "instant_deploy": False
}))
PY
)
  APP_UUID=$(api POST /api/v1/applications/public "$PAYLOAD" | jq_get uuid)
fi
echo "   app_uuid=$APP_UUID"

# ---------- 3. set env vars in bulk ----------
echo ">> Setting environment variables..."

env_item() { # key value [is_literal]
  python3 -c "
import json,sys
print(json.dumps({
  'key':sys.argv[1],
  'value':sys.argv[2],
  'is_literal': sys.argv[3]=='1' if len(sys.argv)>3 else True
}))
" "$1" "$2" "${3:-1}"
}

# Build the env array from currently-exported vars. Only sends what is present.
ENV_PAYLOAD=$(python3 - <<PY
import json, os
keys = [
  "JWT_SECRET",
  "SUPABASE_URL",
  "SUPABASE_PUBLIC_URL",
  "ANON_KEY",
  "SERVICE_ROLE_KEY",
  "DATABASE_URL",
  "ML_MODEL_NAME",
  "ML_DET_THRESHOLD",
  "ML_DET_SIZE",
  "CLUSTER_MAX_DISTANCE",
  "CLUSTER_MIN_FACES",
  "CORS_ORIGINS",
  "SERVICE_FQDN_WEB",
  "SERVICE_FQDN_API",
]
data = []
for k in keys:
    v = os.environ.get(k)
    if v is None or v == "":
        continue
    data.append({"key": k, "value": v, "is_literal": True})
print(json.dumps({"data": data}))
PY
)

api PATCH "/api/v1/applications/$APP_UUID/envs/bulk" "$ENV_PAYLOAD" >/dev/null
echo "   envs set."

# ---------- 4. deploy ----------
echo ">> Triggering deploy..."
DEPLOY_RES=$(api GET "/api/v1/deploy?uuid=$APP_UUID&force=false")
echo "$DEPLOY_RES"

echo
echo "==========================="
echo " App URL (admin):    $COOLIFY_URL/project/$PROJECT_UUID/application/$APP_UUID"
echo " Web FQDN (target):  https://${SERVICE_FQDN_WEB:-not-set-yet}"
echo " API FQDN (target):  https://${SERVICE_FQDN_API:-not-set-yet}"
echo "==========================="
