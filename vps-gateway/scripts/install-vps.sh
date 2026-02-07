#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "[sandalphone] run as root: sudo bash install-vps.sh"
  exit 1
fi

APP_USER="${APP_USER:-sandalphone}"
APP_DIR="${APP_DIR:-/opt/sandalphone/vps-gateway}"
REPO_URL="${REPO_URL:-git@github.com:mattwiebe/sandalphone.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
PORT="${PORT:-8080}"

OUTBOUND_TARGET_E164="${OUTBOUND_TARGET_E164:-}"
TWILIO_AUTH_TOKEN="${TWILIO_AUTH_TOKEN:-}"
PUBLIC_BASE_URL="${PUBLIC_BASE_URL:-}"
TWILIO_PHONE_NUMBER="${TWILIO_PHONE_NUMBER:-}"
VOIPMS_DID="${VOIPMS_DID:-}"
ASSEMBLYAI_API_KEY="${ASSEMBLYAI_API_KEY:-}"
GOOGLE_TRANSLATE_API_KEY="${GOOGLE_TRANSLATE_API_KEY:-}"
AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
AWS_REGION="${AWS_REGION:-us-west-2}"
POLLY_VOICE_EN="${POLLY_VOICE_EN:-Joanna}"
POLLY_VOICE_ES="${POLLY_VOICE_ES:-Lupe}"
OPENCLAW_BRIDGE_URL="${OPENCLAW_BRIDGE_URL:-}"
OPENCLAW_BRIDGE_API_KEY="${OPENCLAW_BRIDGE_API_KEY:-}"
OPENCLAW_BRIDGE_TIMEOUT_MS="${OPENCLAW_BRIDGE_TIMEOUT_MS:-1200}"

ASTERISK_SHARED_SECRET="${ASTERISK_SHARED_SECRET:-}"
CONTROL_API_SECRET="${CONTROL_API_SECRET:-}"

TAILSCALE_AUTHKEY="${TAILSCALE_AUTHKEY:-}"
TAILSCALE_HOSTNAME="${TAILSCALE_HOSTNAME:-sandalphone}"

log() {
  echo "[sandalphone] $*"
}

print_api_key_guide() {
  cat <<'EOF'
[sandalphone] API keys are optional for install, but required for real translation.

STT (AssemblyAI):
  - Create an account, then generate an API key.
  - Docs: https://www.assemblyai.com/docs

Translation (Google Cloud Translate v2):
  - Create a Google Cloud project and enable "Cloud Translation API".
  - Create an API key restricted to Translation API.
  - Docs: https://cloud.google.com/translate/docs/basic/quickstart

TTS (AWS Polly Standard):
  - Create an IAM user with Polly permissions.
  - Create access key + secret key.
  - Docs: https://docs.aws.amazon.com/polly/latest/dg/setting-up.html

You can re-run this installer later with keys, or edit /opt/sandalphone/vps-gateway/.env directly.
EOF
}

prompt_required() {
  local name="$1"
  local label="$2"
  local value="${!name:-}"
  if [[ -n "${value}" ]]; then
    return 0
  fi
  if [[ -t 0 ]]; then
    read -r -p "${label}: " value
  elif [[ -t 1 && -e /dev/tty ]]; then
    read -r -p "${label}: " value </dev/tty
  fi
  if [[ -z "${value}" ]]; then
    echo "[sandalphone] missing required: ${name}"
    exit 1
  fi
  printf -v "${name}" "%s" "${value}"
}

ensure_user() {
  if ! id -u "${APP_USER}" >/dev/null 2>&1; then
    log "creating user ${APP_USER}"
    adduser --disabled-password --gecos "" "${APP_USER}"
  fi
}

ensure_dirs() {
  mkdir -p "$(dirname "${APP_DIR}")"
  chown -R "${APP_USER}:${APP_USER}" "$(dirname "${APP_DIR}")"
}

ensure_node() {
  if command -v node >/dev/null 2>&1; then
    local version
    version="$(node -v | sed 's/^v//')"
    if [[ "${version%%.*}" -ge 22 ]]; then
      return 0
    fi
  fi
  log "installing Node 22"
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
}

ensure_deps() {
  log "installing base packages"
  apt-get update -y
  apt-get install -y git curl ca-certificates
}

ensure_tailscale() {
  log "installing tailscale"
  if ! command -v tailscale >/dev/null 2>&1; then
    curl -fsSL https://tailscale.com/install.sh | sh
  fi
  if [[ -n "${TAILSCALE_AUTHKEY}" ]]; then
    log "bringing up tailscale"
    tailscale up --authkey "${TAILSCALE_AUTHKEY}" --hostname "${TAILSCALE_HOSTNAME}" --ssh || true
  else
    log "TAILSCALE_AUTHKEY not set; skipping tailscale up"
  fi
}

discover_funnel_url() {
  local url=""
  local status
  status="$(tailscale funnel status 2>/dev/null || true)"
  url="$(echo "${status}" | grep -Eo 'https://[^ ]+' | head -n 1 || true)"
  if [[ -z "${url}" ]]; then
    url="$(echo "${status}" | grep -Eo '[a-zA-Z0-9.-]+\.ts\.net' | head -n 1 || true)"
    if [[ -n "${url}" ]]; then
      url="https://${url}"
    fi
  fi
  echo "${url}"
}

setup_funnel() {
  log "configuring tailscale funnel"
  if ! tailscale funnel --bg --yes "${PORT}"; then
    log "funnel not enabled or failed; check https://login.tailscale.com/f/funnel"
    return 0
  fi
  local url
  url="$(discover_funnel_url)"
  if [[ -n "${url}" ]]; then
    PUBLIC_BASE_URL="${url}"
    log "detected funnel url ${PUBLIC_BASE_URL}"
  else
    log "funnel url not detected; run 'tailscale funnel status' to get it"
  fi
}

clone_repo() {
  if [[ -d "${APP_DIR}/.git" ]]; then
    log "updating repo"
    sudo -u "${APP_USER}" -H bash -lc "cd ${APP_DIR} && git fetch origin && git checkout ${REPO_BRANCH} && git pull --ff-only origin ${REPO_BRANCH}"
  else
    log "cloning repo"
    sudo -u "${APP_USER}" -H bash -lc "mkdir -p ${APP_DIR} && git clone ${REPO_URL} ${APP_DIR} && cd ${APP_DIR} && git checkout ${REPO_BRANCH}"
  fi
}

build_app() {
  log "installing npm deps"
  sudo -u "${APP_USER}" -H bash -lc "cd ${APP_DIR} && npm install"
  log "building"
  sudo -u "${APP_USER}" -H bash -lc "cd ${APP_DIR} && npm run build"
}

set_env_key() {
  local file="$1"
  local key="$2"
  local value="$3"
  if grep -q "^${key}=" "${file}"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "${file}"
  else
    printf "%s=%s\n" "${key}" "${value}" >> "${file}"
  fi
}

write_env() {
  local env_path="${APP_DIR}/.env"
  if [[ ! -f "${env_path}" ]]; then
    cp "${APP_DIR}/.env.example" "${env_path}"
  fi

  if [[ -z "${ASTERISK_SHARED_SECRET}" ]]; then
    ASTERISK_SHARED_SECRET="$(openssl rand -hex 16)"
  fi
  if [[ -z "${CONTROL_API_SECRET}" ]]; then
    CONTROL_API_SECRET="$(openssl rand -hex 16)"
  fi

  set_env_key "${env_path}" "PORT" "${PORT}"
  set_env_key "${env_path}" "OUTBOUND_TARGET_E164" "${OUTBOUND_TARGET_E164}"
  set_env_key "${env_path}" "TWILIO_AUTH_TOKEN" "${TWILIO_AUTH_TOKEN}"
  set_env_key "${env_path}" "PUBLIC_BASE_URL" "${PUBLIC_BASE_URL}"
  set_env_key "${env_path}" "TWILIO_PHONE_NUMBER" "${TWILIO_PHONE_NUMBER}"
  set_env_key "${env_path}" "VOIPMS_DID" "${VOIPMS_DID}"
  set_env_key "${env_path}" "ASTERISK_SHARED_SECRET" "${ASTERISK_SHARED_SECRET}"
  set_env_key "${env_path}" "CONTROL_API_SECRET" "${CONTROL_API_SECRET}"
  set_env_key "${env_path}" "ASSEMBLYAI_API_KEY" "${ASSEMBLYAI_API_KEY}"
  set_env_key "${env_path}" "GOOGLE_TRANSLATE_API_KEY" "${GOOGLE_TRANSLATE_API_KEY}"
  set_env_key "${env_path}" "AWS_ACCESS_KEY_ID" "${AWS_ACCESS_KEY_ID}"
  set_env_key "${env_path}" "AWS_SECRET_ACCESS_KEY" "${AWS_SECRET_ACCESS_KEY}"
  set_env_key "${env_path}" "AWS_REGION" "${AWS_REGION}"
  set_env_key "${env_path}" "POLLY_VOICE_EN" "${POLLY_VOICE_EN}"
  set_env_key "${env_path}" "POLLY_VOICE_ES" "${POLLY_VOICE_ES}"
  set_env_key "${env_path}" "OPENCLAW_BRIDGE_URL" "${OPENCLAW_BRIDGE_URL}"
  set_env_key "${env_path}" "OPENCLAW_BRIDGE_API_KEY" "${OPENCLAW_BRIDGE_API_KEY}"
  set_env_key "${env_path}" "OPENCLAW_BRIDGE_TIMEOUT_MS" "${OPENCLAW_BRIDGE_TIMEOUT_MS}"

  chown "${APP_USER}:${APP_USER}" "${env_path}"
}

install_service() {
  log "installing systemd unit"
  cp "${APP_DIR}/deploy/systemd/sandalphone-vps-gateway.service" /etc/systemd/system/sandalphone-vps-gateway.service
  systemctl daemon-reload
  systemctl enable --now sandalphone-vps-gateway
}

health_check() {
  log "health check"
  curl -fsSL "http://127.0.0.1:${PORT}/health" >/dev/null
}

prompt_required OUTBOUND_TARGET_E164 "Outbound target phone (E.164)"

print_api_key_guide

ensure_deps
ensure_node
ensure_user
ensure_dirs
clone_repo
ensure_tailscale
setup_funnel
build_app
write_env
install_service
health_check

log "install complete"
if [[ -n "${PUBLIC_BASE_URL}" ]]; then
  log "Twilio Voice webhook: ${PUBLIC_BASE_URL}/twilio/voice"
  log "Twilio Media Stream: wss://${PUBLIC_BASE_URL#https://}/twilio/stream"
else
  log "PUBLIC_BASE_URL not set; configure and restart service"
fi
