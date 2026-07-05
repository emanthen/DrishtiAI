#!/usr/bin/env bash
# Usage: ./tests/smoke_test.sh
# Env:   API_URL (default http://localhost:8000)
#        SEED_EMAIL / SEED_PASS (default seed script values)
set -euo pipefail

API="${API_URL:-http://localhost:8000}"
EMAIL="${SEED_EMAIL:-admin@drishtiai.local}"
PASS="${SEED_PASS:-devpassword123}"

PASS_COUNT=0
FAIL_COUNT=0

ok()   { echo "  [PASS] $1"; PASS_COUNT=$((PASS_COUNT+1)); }
fail() { echo "  [FAIL] $1 — $2"; FAIL_COUNT=$((FAIL_COUNT+1)); }

echo "=== DrishtiAI smoke test — $API ==="

# Login
echo "→ Login"
LOGIN=$(curl -sf -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}") || { echo "[FAIL] Login request failed"; exit 1; }
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "  token: ${TOKEN:0:20}…"

check() {
  local label="$1" url="$2"
  STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
    -H "Authorization: Bearer $TOKEN" "$API$url" 2>/dev/null || echo "000")
  if [[ "$STATUS" =~ ^2 ]]; then
    ok "$label ($STATUS)"
  else
    fail "$label" "HTTP $STATUS"
  fi
}

echo "→ Core endpoints"
check "GET /system/health"       "/system/health"
check "GET /cameras"             "/cameras"
check "GET /events"              "/events?limit=1&days=1"
check "GET /analytics/overview"  "/analytics/overview"

echo "→ PR-specific endpoints"
check "GET /analytics/vehicle-colors" "/analytics/vehicle-colors?days=30"
check "GET /analytics/vehicle-types"  "/analytics/vehicle-types?days=30"
check "GET /analytics/dwell-time"     "/analytics/dwell-time?days=14"
check "GET /analytics/camera-activity""/analytics/camera-activity?days=7"
check "GET /plates/search"            "/plates/search?q=BA"
check "GET /system/db-stats"          "/system/db-stats"
check "GET /watchlists"               "/watchlists"
check "GET /alerts"                   "/alerts?limit=1"

echo ""
echo "=== Results: $PASS_COUNT passed, $FAIL_COUNT failed ==="
[[ $FAIL_COUNT -eq 0 ]] && exit 0 || exit 1
