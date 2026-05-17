#!/usr/bin/env bash
# Fix Coolify local -> macOS host SSH connectivity.
#
# Run from the Mac host (NOT inside any container).
# Requirements: COOLIFY_URL + COOLIFY_TOKEN exported, or scripts/.coolify.env present.

set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE="scripts/.coolify.env"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a; source "$ENV_FILE"; set +a
fi

: "${COOLIFY_URL:?missing COOLIFY_URL}"
: "${COOLIFY_TOKEN:?missing COOLIFY_TOKEN}"

H=(-H "Authorization: Bearer $COOLIFY_TOKEN" -H "Content-Type: application/json")

echo ">> 1. Fetching Coolify public key..."
PUBKEY=$(curl -sS "${H[@]}" "$COOLIFY_URL/api/v1/security/keys" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['public_key'].strip())")
echo "   key: ${PUBKEY:0:50}..."

echo ">> 2. Adding key to ~/.ssh/authorized_keys (idempotent)..."
mkdir -p ~/.ssh
chmod 700 ~/.ssh
touch ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
if ! grep -qF "$PUBKEY" ~/.ssh/authorized_keys; then
  echo "$PUBKEY" >> ~/.ssh/authorized_keys
  echo "   added."
else
  echo "   already present."
fi

echo ">> 3. Checking Remote Login (sshd)..."
if sudo -n systemsetup -getremotelogin 2>/dev/null | grep -qi "On"; then
  echo "   Remote Login is ON."
else
  echo "   Remote Login is OFF or sudo required."
  echo "   Run manually: sudo systemsetup -setremotelogin on"
  echo "   Or System Settings → General → Sharing → Remote Login → On"
fi

echo ">> 4. Checking sshd is listening on :22..."
if lsof -iTCP:22 -sTCP:LISTEN -P >/dev/null 2>&1; then
  echo "   sshd OK."
else
  echo "   sshd is NOT listening on :22. Enable Remote Login first."
  exit 1
fi

echo ">> 5. Discovering Coolify network gateway (host IP from Coolify's view)..."
GATEWAY=$(docker network inspect coolify 2>/dev/null \
  | python3 -c "
import sys,json
try:
    nets=json.load(sys.stdin)
    for n in nets:
        for cfg in n.get('IPAM',{}).get('Config',[]):
            gw=cfg.get('Gateway')
            if gw:
                print(gw); break
except Exception:
    pass
")
if [[ -n "$GATEWAY" ]]; then
  echo "   gateway: $GATEWAY  (use this as Server IP, or 'host.docker.internal')"
else
  echo "   couldn't auto-detect — use 'host.docker.internal' in the Coolify UI."
fi

echo ">> 6. Testing local SSH login as $(whoami)..."
if ssh -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=3 \
      "$(whoami)@localhost" echo OK 2>/dev/null; then
  echo "   local SSH OK."
else
  echo "   local SSH FAILED. Check:"
  echo "   - Remote Login enabled (System Settings → Sharing)"
  echo "   - User allowed under 'Only these users'"
  echo "   - macOS firewall allows sshd:"
  echo "       sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/sbin/sshd"
  echo "       sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp /usr/sbin/sshd"
fi

echo
echo "==========================================="
echo " Next steps in Coolify UI (Servers → localhost):"
echo "   IP / Domain : host.docker.internal   (or $GATEWAY)"
echo "   User        : $(whoami)"
echo "   Port        : 22"
echo "   Click 'Validate Server'."
echo "==========================================="
