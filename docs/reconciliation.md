# DrishtiAI — Capability Reconciliation

**Generated:** 2026-07-05
**Verified against:** `master` @ `f794025` (37 commits)
**Method:** manual inspection of every file claimed by the README and CHANGELOG.

---

## How to read this table

| Column | Meaning |
|---|---|
| **Claimed in README** | Feature appeared in the README capability table before this reconciliation |
| **Actually on master** | Code implementing the feature exists and is wired up in the live service |
| **Tests exist** | At least one automated test or benchmark covers the feature |
| **Status** | `done` · `present-no-tests` · `partial` · `absent` |

---

## Capability audit

| Capability | Claimed in README | Actually on master | Tests exist | Status | Notes |
|---|---|---|---|---|---|
| **ANPR — plate detection** | ✅ | ✅ `pipeline/ocr.py` | ✅ `eval_phase1.py` | done | Two-stage OpenCV→PaddleOCR; confidence-weighted multi-frame voter |
| **ANPR — Nepali normalisation** | ❌ (was missing) | ✅ `_normalize_np_plate()` | ✅ `eval_phase11.py` | done | Province prefix, zero-padded form; motorcycle two-row detection |
| **ANPR — benchmark results** | ❌ | ⚠️ evaluators exist; no published pass/fail numbers on real Nepali footage | ✅ synthetic only | partial | `eval_phase1.py` runs against synthetic video only; no real-world dataset |
| **Parking management** | ✅ | ✅ `pipeline/parking_session.py` | ✅ smoke test | done | Entry/exit session, tiered tariff, NPR billing, manual waive/close |
| **Gate control** | ✅ | ✅ `pipeline/gate.py` | ❌ no unit tests | present-no-tests | Webhook + ONVIF drivers; license-gated since PR 11 |
| **Alert engine** | ✅ | ✅ `pipeline/alert_engine.py` | ✅ smoke test | done | Exact/prefix/fuzzy watchlist matching; push notifications |
| **Visitor passes** | ✅ | ✅ `routers/visitor_passes.py` | ✅ smoke test | done | Single-use enforcement; cancel = immediate lockout |
| **User management / RBAC** | ✅ | ✅ `routers/users.py` + `deps.py` | ✅ `test_security.py` | done | 6-level role hierarchy; per-site scoping; superadmin management |
| **Reports & exports** | ✅ | ✅ `routers/reports.py` + `tasks/reports.py` | ✅ smoke test | done | CSV (events/parking/alerts) + PDF via reportlab; async Celery export |
| **Audit log** | ✅ | ✅ `audit.py` + `routers/audit.py` | ✅ smoke test | done | Append-only; no UPDATE/DELETE paths; actor+IP+metadata |
| **Webhooks** | ✅ | ✅ `pipeline/webhook_fire.py` + `routers/webhooks.py` | ✅ smoke test | done | HMAC-SHA256 signed; 7 event types; test-ping endpoint |
| **Mobile app** | ✅ | ✅ `apps/mobile/` (Expo Router v3) | ❌ no tests | present-no-tests | 5 screens (Home/Passes/Alerts/Profile/Login); no Detox/Jest tests; not production-validated |
| **Observability** | ✅ | ✅ `deploy/compose/grafana/` | ❌ no tests | present-no-tests | Prometheus + Grafana + Loki; auto-provisioned dashboard; working docker-compose profile |
| **Vehicle intelligence** | ❌ (was missing) | ✅ `routers/vehicles.py` | ✅ smoke test | done | Color + type classification; `/vehicles` search; `VehicleDetail` with plate list |
| **Vehicle make/model** | ❌ | ❌ | ❌ | absent | No model classifier; planned for Phase 3 extension |
| **Vehicle direction** | ❌ | ❌ | ❌ | absent | Not implemented |
| **Review queue** | ❌ (was missing) | ✅ `routers/review_queue.py` | ✅ smoke test | done | Low-confidence detections → human review flywheel |
| **Investigation / plate search** | ❌ (was missing) | ✅ `routers/plates.py` | ✅ smoke test | done | pg_trgm fuzzy search; per-plate timeline; camera sightings |
| **Camera map** | ❌ | ❌ | ❌ | absent | No geospatial camera-map UI |
| **Scale — partitioned events** | ❌ | ✅ `alembic/versions/0007_event_partitions.py` | ❌ no load test | present-no-tests | Monthly partitions; `partition_manager.py` at startup; no load test against 30–100 cameras |
| **Scale — DeepStream** | ❌ | ❌ | ❌ | absent | GStreamer pipeline only; DeepStream path planned but not started |
| **Licensing** | ❌ (was missing) | ✅ `packages/licensing/` | ✅ 4 test files | done | Ed25519 node-lock; offline expiry; degrade-don't-brick; clock guard; operator CLI |
| **Security — Argon2id** | ❌ | ✅ `auth/password.py` | ✅ `test_security.py` | done | Argon2id (t=3, m=65536, p=4); parameter test asserts specific values |
| **Security — RS256 JWT** | ❌ | ✅ `auth/jwt.py` | ✅ `test_security.py` | done | RS256 asymmetric signing; 15-min access / 7-day refresh; JTI denylist |
| **Security — TOTP MFA** | ❌ | ✅ `routers/mfa.py` | ✅ `test_security.py` | done | TOTP enrollment, verify, disable; required at login when enrolled |
| **Security — rate limit + lockout** | ❌ | ✅ `auth/lockout.py` + `limiter.py` | ✅ `test_security.py` | done | Progressive lockout (5/10/30 min); `slowapi` per-IP rate limiting |
| **Security — SSRF protection** | ❌ | ✅ `http_safe.py` | ✅ `test_security.py` | done | URL allowlist for webhook/gate targets; blocks RFC-1918 + localhost |
| **Security — input validation** | ❌ | ✅ Pydantic on all request bodies | ⚠️ partial | partial | Pydantic schemas; no fuzz/injection test suite |
| **Security — CI gates** | ❌ | ⚠️ GitHub Actions lint+typecheck+tests | ❌ no SAST | partial | No Bandit/Semgrep/Trivy in CI; no secret-scanning gate |
| **Installer wizard** | ❌ | ❌ `deploy/install/` is empty | ❌ | absent | Directory exists; no content |
| **Backup / restore** | ❌ | ⚠️ `make backup` (pg_dump) | ❌ no restore test | partial | Dump runs; no automated restore round-trip test |
| **Watchdog / auto-restart** | ❌ | ❌ | ❌ | absent | Docker `restart: unless-stopped` only; no pipeline watchdog |
| **Demo / seed data** | ❌ | ✅ `seed_dev_data.py` (300 events, 8 vehicles) | ✅ smoke test | done | 30-day realistic dataset; reproducible with `Random(42)` |
| **Beyond-ANPR analytics (zone/wrong-way/helmet)** | ❌ | ❌ | ❌ | absent | No zone editor, wrong-way detection, illegal parking, helmet, line count, tamper |

---

## README changes made (this commit)

1. Added `Licensing`, `Nepali plate normalisation`, `Vehicle intelligence`, `Review queue`, `Investigation` to capability table.
2. Removed "default credentials: `admin` / `admin`" Grafana reference — replaced with generated-credential instructions.
3. Fixed `GRAFANA_PASSWORD` env-var table entry from "No / default: admin" to "Yes / generated at install".
4. Added `packages/licensing/` and `apps/licensing/` to repo layout.
5. Added missing API endpoints to API reference: `/plates`, `/vehicles`, `/review-queue`, `/system/license`, TOTP to `/auth`.

---

## Items still needing action

| Item | Priority | Recommended next step |
|---|---|---|
| Real Nepali OCR benchmark | High | Record numbers on actual plate footage; publish in `ml/benchmarks/nepali-ocr.md` |
| Gate unit tests | High | Add `test_gate.py` to `packages/licensing/tests/` (already has enforcement tests); add pipeline gate tests |
| Mobile app tests | Medium | Add Jest/React Native Testing Library for critical flows (login, pass create) |
| CI security gates (Bandit, Trivy) | High | Add `.github/workflows/security.yml` |
| SSRF fuzz / injection test suite | Medium | Extend `test_security.py` |
| Installer wizard | Medium | `deploy/install/install.sh` — generate secrets, run migrations, set GRAFANA_PASSWORD |
| Backup restore round-trip test | Medium | Add `make test-backup-restore` |
| Watchdog | Low | Docker `restart: always` is basic; add a dedicated health-check → restart loop for pipeline |
| Vehicle make/model | Low | Phase 4 ML work |
| DeepStream / scale load test | Low | Phase 7 |
