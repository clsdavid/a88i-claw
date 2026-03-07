#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${AUTOCRAB_IMAGE:-${CLAWDBOT_IMAGE:-autocrab:local}}"
CONFIG_DIR="${AUTOCRAB_CONFIG_DIR:-${CLAWDBOT_CONFIG_DIR:-$HOME/.autocrab}}"
WORKSPACE_DIR="${AUTOCRAB_WORKSPACE_DIR:-${CLAWDBOT_WORKSPACE_DIR:-$HOME/.autocrab/workspace}}"
PROFILE_FILE="${AUTOCRAB_PROFILE_FILE:-${CLAWDBOT_PROFILE_FILE:-$HOME/.profile}}"

PROFILE_MOUNT=()
if [[ -f "$PROFILE_FILE" ]]; then
  PROFILE_MOUNT=(-v "$PROFILE_FILE":/home/node/.profile:ro)
fi

echo "==> Build image: $IMAGE_NAME"
docker build -t "$IMAGE_NAME" -f "$ROOT_DIR/Dockerfile" "$ROOT_DIR"

echo "==> Run live model tests (profile keys)"
docker run --rm -t \
  --entrypoint bash \
  -e COREPACK_ENABLE_DOWNLOAD_PROMPT=0 \
  -e HOME=/home/node \
  -e NODE_OPTIONS=--disable-warning=ExperimentalWarning \
  -e AUTOCRAB_LIVE_TEST=1 \
  -e AUTOCRAB_LIVE_MODELS="${AUTOCRAB_LIVE_MODELS:-${CLAWDBOT_LIVE_MODELS:-modern}}" \
  -e AUTOCRAB_LIVE_PROVIDERS="${AUTOCRAB_LIVE_PROVIDERS:-${CLAWDBOT_LIVE_PROVIDERS:-}}" \
  -e AUTOCRAB_LIVE_MAX_MODELS="${AUTOCRAB_LIVE_MAX_MODELS:-${CLAWDBOT_LIVE_MAX_MODELS:-48}}" \
  -e AUTOCRAB_LIVE_MODEL_TIMEOUT_MS="${AUTOCRAB_LIVE_MODEL_TIMEOUT_MS:-${CLAWDBOT_LIVE_MODEL_TIMEOUT_MS:-}}" \
  -e AUTOCRAB_LIVE_REQUIRE_PROFILE_KEYS="${AUTOCRAB_LIVE_REQUIRE_PROFILE_KEYS:-${CLAWDBOT_LIVE_REQUIRE_PROFILE_KEYS:-}}" \
  -v "$CONFIG_DIR":/home/node/.autocrab \
  -v "$WORKSPACE_DIR":/home/node/.autocrab/workspace \
  "${PROFILE_MOUNT[@]}" \
  "$IMAGE_NAME" \
  -lc "set -euo pipefail; [ -f \"$HOME/.profile\" ] && source \"$HOME/.profile\" || true; cd /app && pnpm test:live"
