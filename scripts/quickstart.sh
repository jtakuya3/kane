#!/usr/bin/env bash
# Kane one-shot quickstart for a fresh Ubuntu/Debian VPS.
#
# Run on the VPS as a sudo-capable user, from the repo root:
#
#     bash scripts/quickstart.sh
#
# What it does:
#   1. Installs Docker + docker compose plugin if missing.
#   2. Detects the public IPv4 and uses <ip-with-dashes>.sslip.io as KANE_HOST,
#      so HTTPS works with no DNS setup.
#   3. Generates a random KANE_ACCESS_TOKEN (or reuses an existing one in .env).
#   4. Prompts for OPENAI_API_KEY if missing.
#   5. Opens UFW for 80/443 if UFW is active.
#   6. Builds and starts the stack with docker compose, waits for the cert,
#      and prints the URL + password.

set -euo pipefail

C_BLUE='\033[1;34m'; C_GREEN='\033[1;32m'; C_YELLOW='\033[1;33m'; C_RED='\033[1;31m'; C_RESET='\033[0m'
say()  { printf "${C_BLUE}==>${C_RESET} %s\n" "$*"; }
ok()   { printf "${C_GREEN}✔${C_RESET}  %s\n" "$*"; }
warn() { printf "${C_YELLOW}!${C_RESET}  %s\n" "$*"; }
die()  { printf "${C_RED}✖ %s${C_RESET}\n" "$*" >&2; exit 1; }

[[ -f docker-compose.yml ]] || die "Run this from the repo root (docker-compose.yml not found)."

# ---------------------------------------------------------------------------
# 1. Sudo
# ---------------------------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
  if ! command -v sudo >/dev/null; then die "Run as root or install sudo."; fi
  SUDO="sudo"
else
  SUDO=""
fi

# ---------------------------------------------------------------------------
# 2. Docker
# ---------------------------------------------------------------------------
if ! command -v docker >/dev/null; then
  say "Installing Docker (via get.docker.com)…"
  curl -fsSL https://get.docker.com | $SUDO sh
  ok "Docker installed."
else
  ok "Docker already installed: $(docker --version)"
fi

if ! docker compose version >/dev/null 2>&1; then
  say "Installing docker compose plugin…"
  $SUDO apt-get update -y
  $SUDO apt-get install -y docker-compose-plugin
fi
ok "docker compose: $(docker compose version)"

# Allow the current user to run docker without sudo (effective on next login).
if [[ -n "$SUDO" ]] && ! id -nG "$USER" | grep -qw docker; then
  $SUDO usermod -aG docker "$USER" || true
  warn "Added $USER to docker group. Take effect after re-login (or use sudo for now)."
fi

DOCKER="docker"
if [[ -n "$SUDO" ]] && ! docker info >/dev/null 2>&1; then
  DOCKER="$SUDO docker"
fi

# ---------------------------------------------------------------------------
# 3. Public IP -> sslip.io hostname
# ---------------------------------------------------------------------------
say "Detecting public IPv4…"
IP=$(curl -4 -s --max-time 5 ifconfig.me \
     || curl -4 -s --max-time 5 https://api.ipify.org \
     || true)
[[ -n "$IP" ]] || die "Could not detect public IPv4. Set KANE_HOST in .env manually."
HOST_DEFAULT="${IP//./-}.sslip.io"
ok "Public IP: $IP   →   default KANE_HOST: $HOST_DEFAULT"

# ---------------------------------------------------------------------------
# 4. .env
# ---------------------------------------------------------------------------
if [[ ! -f .env ]]; then
  cp .env.example .env
  ok "Created .env from .env.example"
fi

# Read existing values (if any) so we never overwrite a real key.
get_env() { grep -E "^$1=" .env 2>/dev/null | head -n1 | cut -d= -f2- | tr -d "'\"" || true; }
set_env() {
  local key="$1" val="$2"
  if grep -qE "^$key=" .env; then
    # macOS/Linux portable in-place replace
    python3 - "$key" "$val" <<'PY'
import sys, re, pathlib
key, val = sys.argv[1], sys.argv[2]
p = pathlib.Path(".env"); src = p.read_text()
p.write_text(re.sub(rf"(?m)^{re.escape(key)}=.*$", f"{key}={val}", src))
PY
  else
    printf "%s=%s\n" "$key" "$val" >> .env
  fi
}

# OpenAI API key (prompt only if missing or still the placeholder).
existing_key=$(get_env OPENAI_API_KEY)
if [[ -z "$existing_key" || "$existing_key" == "sk-..." ]]; then
  printf "%s" "Paste your OpenAI API key (sk-...): " >&2
  read -rs OPENAI_KEY; echo
  [[ "$OPENAI_KEY" =~ ^sk- ]] || die "That doesn't look like an OpenAI key."
  set_env OPENAI_API_KEY "$OPENAI_KEY"
  ok "OPENAI_API_KEY saved."
else
  ok "OPENAI_API_KEY already set in .env."
fi

# Access token: keep existing if non-default, else generate.
existing_token=$(get_env KANE_ACCESS_TOKEN)
if [[ -z "$existing_token" || "$existing_token" == "change-me-please" ]]; then
  TOKEN=$(openssl rand -hex 16)
  set_env KANE_ACCESS_TOKEN "$TOKEN"
  ok "Generated KANE_ACCESS_TOKEN."
else
  TOKEN="$existing_token"
  ok "Re-using existing KANE_ACCESS_TOKEN from .env."
fi

# Host (always set to sslip.io default unless user already customised it).
existing_host=$(get_env KANE_HOST)
if [[ -z "$existing_host" || "$existing_host" == "kane-yours.duckdns.org" ]]; then
  set_env KANE_HOST "$HOST_DEFAULT"
  HOST="$HOST_DEFAULT"
else
  HOST="$existing_host"
fi
ok "KANE_HOST = $HOST"

# Let's Encrypt e-mail
existing_email=$(get_env LETSENCRYPT_EMAIL)
if [[ -z "$existing_email" || "$existing_email" == "you@example.com" ]]; then
  set_env LETSENCRYPT_EMAIL "admin@${HOST}"
fi

# ---------------------------------------------------------------------------
# 5. Firewall
# ---------------------------------------------------------------------------
if command -v ufw >/dev/null && $SUDO ufw status | grep -q "Status: active"; then
  say "Opening 80/443 in ufw…"
  $SUDO ufw allow 80/tcp || true
  $SUDO ufw allow 443/tcp || true
fi

# ---------------------------------------------------------------------------
# 6. Build & up
# ---------------------------------------------------------------------------
say "Building and starting containers…"
$DOCKER compose pull --ignore-pull-failures || true
$DOCKER compose up -d --build

# ---------------------------------------------------------------------------
# 7. Wait for HTTPS to come online
# ---------------------------------------------------------------------------
say "Waiting for Caddy to obtain a Let's Encrypt cert (this can take ~30s)…"
for i in $(seq 1 60); do
  if curl -ksS -m 4 "https://$HOST/api/health" | grep -q '"ok"'; then
    ok "HTTPS endpoint is live."
    break
  fi
  sleep 2
  if [[ $i -eq 60 ]]; then
    warn "Timed out waiting for HTTPS. Check: $DOCKER compose logs caddy"
  fi
done

cat <<EOF

${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}
${C_GREEN}✔ Kane is up.${C_RESET}

  URL:       https://$HOST
  Password:  $TOKEN

  Open the URL on your phone, enter the password, allow the
  microphone, then tap START. Speak in English or Japanese —
  it will translate to the other.

  Logs:      $DOCKER compose logs -f
  Stop:      $DOCKER compose down
  Update:    git pull && $DOCKER compose up -d --build
${C_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${C_RESET}
EOF
