#!/usr/bin/env bash
# Backup → restore round-trip test.
#
# Verifies that a pg_dump backup can be fully restored into a fresh Postgres
# volume and that the API comes back healthy with the same row counts.
#
# Usage:
#   bash deploy/install/test_backup_restore.sh
#
# Requirements:
#   - Full stack already running (make dev or docker compose up -d)
#   - .env loaded / POSTGRES_PASSWORD available
#   - jq installed (sudo apt-get install jq)
#
# Exit codes:
#   0 — backup and restore succeeded; row counts match
#   1 — any failure

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE="docker compose -f $REPO_ROOT/deploy/compose/docker-compose.yml"
BACKUP_DIR="$REPO_ROOT/deploy/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/test_restore_${TIMESTAMP}.sql"

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
die()  { echo -e "${RED}✗ FAIL:${NC} $*" >&2; exit 1; }
step() { echo -e "\n${CYAN}▶ $*${NC}"; }

# ── Dependency check ──────────────────────────────────────────────────────────
command -v jq >/dev/null 2>&1 || die "jq not found. Run: sudo apt-get install jq"
mkdir -p "$BACKUP_DIR"

# ── 1. Record pre-backup row counts ──────────────────────────────────────────
step "Recording pre-backup row counts"

count_rows() {
  $COMPOSE exec -T postgres psql -U drishtiai -d drishtiai -t -c "SELECT COUNT(*) FROM $1;" \
    | tr -d '[:space:]'
}

PRE_EVENTS=$(count_rows events)
PRE_CAMERAS=$(count_rows cameras)
PRE_USERS=$(count_rows users)
PRE_ORGS=$(count_rows organizations)

echo "  events=$PRE_EVENTS  cameras=$PRE_CAMERAS  users=$PRE_USERS  orgs=$PRE_ORGS"
ok "Row counts recorded"

# Guard: if nothing is seeded, the test is useless
[[ "$PRE_USERS" -gt 0 ]] || die "No users found — run 'make seed-dev' first, then re-run this test"

# ── 2. Create backup ──────────────────────────────────────────────────────────
step "Creating backup → $BACKUP_FILE"
$COMPOSE exec -T postgres pg_dump -U drishtiai drishtiai > "$BACKUP_FILE"
BACKUP_SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
ok "Backup created ($BACKUP_SIZE)"

# ── 3. Stop all services except postgres ─────────────────────────────────────
step "Stopping application services"
$COMPOSE stop api admin worker pipeline web beat 2>/dev/null || true
ok "Application services stopped"

# ── 4. Destroy and recreate the Postgres volume ──────────────────────────────
step "Destroying Postgres volume"
$COMPOSE stop postgres
$COMPOSE rm -f postgres
docker volume rm "$(basename "$REPO_ROOT")_postgres-data" 2>/dev/null \
  || docker volume ls --format '{{.Name}}' | grep postgres | xargs -r docker volume rm
ok "Volume destroyed"

# ── 5. Start fresh Postgres and wait ─────────────────────────────────────────
step "Starting fresh Postgres"
$COMPOSE up -d postgres
echo "Waiting for Postgres to be ready..."
for i in $(seq 1 30); do
  $COMPOSE exec -T postgres pg_isready -U drishtiai -q 2>/dev/null && break
  sleep 2
done
$COMPOSE exec -T postgres pg_isready -U drishtiai -q || die "Postgres did not become ready after restore"
ok "Fresh Postgres ready"

# ── 6. Create database and restore ───────────────────────────────────────────
step "Restoring from backup"
$COMPOSE exec -T postgres psql -U drishtiai -c "DROP DATABASE IF EXISTS drishtiai;" postgres
$COMPOSE exec -T postgres psql -U drishtiai -c "CREATE DATABASE drishtiai;" postgres
$COMPOSE exec -T postgres psql -U drishtiai -d drishtiai < "$BACKUP_FILE"
ok "Restore complete"

# ── 7. Restart application services ──────────────────────────────────────────
step "Restarting application services"
$COMPOSE up -d api admin worker web
echo "Waiting for API to be healthy..."
for i in $(seq 1 30); do
  STATUS=$(curl -sf http://localhost:8000/health 2>/dev/null | jq -r '.ok' 2>/dev/null || echo "false")
  [[ "$STATUS" == "true" ]] && break
  sleep 3
done
[[ "$STATUS" == "true" ]] || die "API did not recover after restore (health check returned: $STATUS)"
ok "API healthy"

# ── 8. Verify row counts match ────────────────────────────────────────────────
step "Verifying row counts"

POST_EVENTS=$(count_rows events)
POST_CAMERAS=$(count_rows cameras)
POST_USERS=$(count_rows users)
POST_ORGS=$(count_rows organizations)

echo "  Before: events=$PRE_EVENTS  cameras=$PRE_CAMERAS  users=$PRE_USERS  orgs=$PRE_ORGS"
echo "  After:  events=$POST_EVENTS cameras=$POST_CAMERAS users=$POST_USERS orgs=$POST_ORGS"

PASS=1
[[ "$POST_EVENTS"  == "$PRE_EVENTS"  ]] || { echo "  MISMATCH: events $PRE_EVENTS → $POST_EVENTS";  PASS=0; }
[[ "$POST_CAMERAS" == "$PRE_CAMERAS" ]] || { echo "  MISMATCH: cameras $PRE_CAMERAS → $POST_CAMERAS"; PASS=0; }
[[ "$POST_USERS"   == "$PRE_USERS"   ]] || { echo "  MISMATCH: users $PRE_USERS → $POST_USERS";   PASS=0; }
[[ "$POST_ORGS"    == "$PRE_ORGS"    ]] || { echo "  MISMATCH: orgs $PRE_ORGS → $POST_ORGS";     PASS=0; }

[[ "$PASS" -eq 1 ]] || die "Row count mismatch after restore — data integrity check failed"

# ── 9. Cleanup test backup ────────────────────────────────────────────────────
rm -f "$BACKUP_FILE"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Backup → restore round-trip: PASSED${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
ok "All $POST_EVENTS events, $POST_cameras cameras, $POST_USERS users intact after restore"
