#!/usr/bin/env bash
set -euo pipefail

cd /repo

export AUTOCRAB_STATE_DIR="/tmp/autocrab-test"
export AUTOCRAB_CONFIG_PATH="${AUTOCRAB_STATE_DIR}/autocrab.json"

echo "==> Build"
pnpm build

echo "==> Seed state"
mkdir -p "${AUTOCRAB_STATE_DIR}/credentials"
mkdir -p "${AUTOCRAB_STATE_DIR}/agents/main/sessions"
echo '{}' >"${AUTOCRAB_CONFIG_PATH}"
echo 'creds' >"${AUTOCRAB_STATE_DIR}/credentials/marker.txt"
echo 'session' >"${AUTOCRAB_STATE_DIR}/agents/main/sessions/sessions.json"

echo "==> Reset (config+creds+sessions)"
pnpm autocrab reset --scope config+creds+sessions --yes --non-interactive

test ! -f "${AUTOCRAB_CONFIG_PATH}"
test ! -d "${AUTOCRAB_STATE_DIR}/credentials"
test ! -d "${AUTOCRAB_STATE_DIR}/agents/main/sessions"

echo "==> Recreate minimal config"
mkdir -p "${AUTOCRAB_STATE_DIR}/credentials"
echo '{}' >"${AUTOCRAB_CONFIG_PATH}"

echo "==> Uninstall (state only)"
pnpm autocrab uninstall --state --yes --non-interactive

test ! -d "${AUTOCRAB_STATE_DIR}"

echo "OK"
