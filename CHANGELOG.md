# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.5.0] — 2026-07-04

### Added — Phase 5: Visitor pass management

**Pipeline**
- `gate.py`: `_check_permit` now returns the `VisitorPass` object (not just bool); after a successful `permit_valid` trigger, single-use passes are automatically marked `used = true` — prevents the gate re-opening on a second drive-by

**API** (`/visitor-passes`)
- `GET /visitor-passes` — paginated list with `site_id`, `status` (active/upcoming/expired/used), cursor filter
- `GET /visitor-passes/mine` — current user's own passes (resident self-service shorthand)
- `POST /visitor-passes` — create: `plate` (auto-normalised), `valid_from`, `valid_to`, `single_use`, `notes`; `site_id` optional (defaults to user's first site)
- `GET /visitor-passes/{id}` — single pass with computed `pass_status`
- `DELETE /visitor-passes/{id}` — cancel (host or site_admin); hard-deletes so gate rule stops matching immediately

**Web dashboard**
- `/visitor-passes` — status tabs (Active / Upcoming / Expired / Used / All); inline "Add pass" form with plate input, datetime-local pickers pre-filled to now → +24h, single-use toggle, notes; Cancel button per pass; Visitor passes nav link added

## [0.4.0] — 2026-07-03

### Added — Phase 4: Gate controller integration

**Models** (`drishtiai_shared.models.gate`)
- `GateController` — site-scoped controller record: `kind` (webhook | onvif), `config` JSONB, `open_pulse_ms`
- `GateRule` — links a camera to a controller with a trigger condition (`any_plate` | `watchlist_match` | `permit_valid`) and optional `watchlist_id`; priority ordering
- `GateTriggerLog` — immutable audit trail of every trigger attempt (rule, event, plate, success, error)
- Alembic migration `0002_gate_controller.py`: `gate_controllers`, `gate_rules`, `gate_trigger_logs`

**Pipeline** (`gate.py`)
- `evaluate_and_trigger`: loads enabled rules for the camera, checks condition (any plate / watchlist entry match with exact+prefix+fuzzy / valid VisitorPass), fires all matching controllers in priority order, writes trigger log row; gate failure never stops the pipeline
- `_WebhookDriver`: stdlib `urllib.request` POST with optional `X-Gate-Secret` header; works with ESP32 relay boards, Hikvision HTTP API, any HTTP-capable controller
- `_OnvifDriver`: raw SOAP `SetRelayOutputState` with WS-Security UsernameToken (SHA-1 password digest); no extra deps; compatible with HikVision DS-2CD/DS-K, Dahua IPC, Axis P-series
- `main.py`: calls `gate.evaluate_and_trigger` after parking session logic

**API** (prefix `/gates`)
- `GET/POST/PATCH/DELETE /gates/controllers` — controller CRUD (site_admin+)
- `POST /gates/controllers/{id}/trigger` — manual open, returns trigger log entry
- `GET /gates/controllers/{id}/log` — recent 50 trigger log entries
- `GET/POST/PATCH/DELETE /gates/rules` — rule CRUD with camera/controller filters

**Web dashboard**
- `/gates` — two-panel layout: controller list (left) + rules table + recent activity log (right); "Open gate" manual trigger button with loading state; enable/disable rules in-place; real-time activity log with success/failure indicator

## [0.3.0] — 2026-07-03

### Added — Phase 3: Parking session tracking

**Model**
- `CameraRole`: added `parking_entry` and `parking_exit` values (VARCHAR column — no migration required)

**Pipeline**
- `parking_session.py`: session lifecycle manager — `parking_entry` cameras open a `ParkingSession` row and set a Redis key (`parking:open:{site_id}:{plate_norm}`, 24 h TTL); `parking_exit` cameras close the session, compute duration, apply the active site tariff, and delete the Redis key; publishes `session_opened` / `session_closed` to `drishti:{site_id}:parking`
- `main.py`: calls `parking_session.on_plate_read` after `alert_engine.check_and_fire`

**Tariff engine** (`_compute_charge`):
- Tiered rules JSON: `grace_minutes`, `tiers` array with `up_to_minutes`/`charge` (flat) or `per_hour`/`max_per_day` entries
- Default dev tariff: NPR 30 for first hour, NPR 30/h thereafter (max NPR 300/day), 10 min grace

**API**
- `GET /parking-sessions` — paginated list with `site_id`, `active_only`, `payment_status`, cursor filters
- `GET /parking-sessions/active` — open sessions (no exit event)
- `GET /parking-sessions/{id}` — single session with denormalised `plate_text`, `entry_ts`, `exit_ts`
- `POST /parking-sessions/{id}/close` — manual close with tariff computation (for missed exit reads)
- `POST /parking-sessions/{id}/mark-paid` — mark as paid
- `POST /parking-sessions/{id}/waive` — waive charge
- `GET/POST/PATCH/DELETE /tariffs` — tariff CRUD (site-scoped, site_admin+)
- `WS /ws/parking` — real-time session open/close feed via Redis pub/sub

**Web dashboard**
- `/parking` — Active / All tabs; live duration counter ticking every second; NPR amount due; Close / Mark paid / Waive action buttons; WebSocket push on session events
- Sidebar nav: added Parking link

**Seed**
- `seed_dev_data.py`: creates `parking_entry` camera (mediamtx/test2) + `parking_exit` camera (mediamtx/test3) + standard tariff

## [0.2.0] — 2026-07-03

### Added — Phase 2: Alert engine, watchlist management, GStreamer pipeline

**Pipeline**
- `gst_capture.py`: GStreamer appsink capture (`rtspsrc → h264parse → avdec_h264 → appsink`); automatic RTSP reconnection with exponential backoff; falls back to OpenCV `StreamCapture` if GStreamer Python bindings are not available
- `voter.py`: Multi-frame plate text voter — accumulates OCR reads over a configurable window (`PIPELINE_VOTER_WINDOW_S=4s`), emits majority-vote consensus when plate exits (`exit_gap_s=1.5s`), requires ≥ `min_reads=2` observations; eliminates single-frame character substitution errors
- `alert_engine.py`: Post-commit watchlist check — exact/prefix/fuzzy plate matching against all active `WatchlistEntry` rows for the site; creates `Alert` rows and publishes to `drishti:{site_id}:alerts` Redis channel
- Pipeline Dockerfile: installs GStreamer packages (`gstreamer1.0-plugins-good/bad/ugly`, `gstreamer1.0-rtsp`, `gstreamer1.0-libav`, `python3-gi`)

**API**
- `GET/POST/PATCH/DELETE /sites` — site CRUD; superadmin + site_admin only for write ops
- `GET/POST/PATCH/DELETE /watchlists` — watchlist CRUD with category (blocked/vip/resident/vendor/staff/police_notice)
- `GET/POST/DELETE /watchlists/{id}/entries` — plate entry management (exact/prefix/fuzzy patterns)
- `GET /alerts` — paginated alert list with site + status filter and cursor pagination
- `GET /alerts/counts` — per-status counts for dashboard badge
- `POST /alerts/{id}/ack|snooze|resolve` — alert lifecycle management
- `WS /ws/alerts` — real-time alert feed via Redis `drishti:*:alerts` pub/sub

**Web dashboard**
- `/alerts` — real-time alert feed with WebSocket push; ack / snooze 1h / resolve actions; status filter tabs; new alerts highlighted with pulse animation
- `/watchlists` — two-panel watchlist manager: list + per-watchlist entry table; add/remove entries with pattern selector; colour-coded category badges
- Sidebar nav: added Alerts and Watchlists links
- `api.ts`: added `sites`, `watchlists`, `alerts` client methods + TypeScript types for all new entities

**Config**
- New pipeline env vars: `PIPELINE_VOTER_WINDOW_S`, `PIPELINE_VOTER_EXIT_GAP_S`, `PIPELINE_VOTER_MIN_READS`, `PIPELINE_CAPTURE_BACKEND`
- mediamtx: added `test2`, `test3` on-demand paths for multi-camera dev testing

## [0.1.0] — 2026-07-03

### Added — Phase 1: Single-camera vertical slice

**Pipeline**
- `apps/pipeline`: OpenCV VideoCapture (RTSP) → PaddleOCR (Apache 2.0, CPU) → plate filter → `PlateDeduplicator` → MinIO snapshot → Postgres `plate_read` event → Redis pub/sub
- `CameraHealthReporter`: daemon thread updates `camera.health_status` every 10s; publishes to `camera:{id}:meta`
- MJPEG live view: pipeline publishes JPEG frames to `camera:{id}:frames`, FastAPI streams as `multipart/x-mixed-replace`

**API**
- JWT auth: HS256 access (15 min) + refresh (7 day) tokens; JTI denylist via Redis; Argon2id password hashing
- `/auth/{login,refresh,logout,me}`, `/cameras`, `/events` (cursor pagination + pg_trgm plate search), `/stream/{id}` MJPEG proxy
- WebSocket endpoints: `WS /ws/events` (all sites), `WS /ws/cameras/{id}` (per-camera)
- Entrypoint runs `alembic upgrade head` before uvicorn starts

**Admin**
- Django 5 proxy models (`managed=False`) for Cameras and Sites — schema owned by Alembic
- Colour-coded `health_badge()` in `CameraAdmin`
- Entrypoint runs `manage.py migrate` + `collectstatic` before gunicorn starts

**Web dashboard**
- Login page → Zustand auth store (localStorage persist)
- Live view: camera tiles with MJPEG stream + health dot; WebSocket event feed (last 100, 2s highlight)
- Events table: 300ms debounced pg_trgm plate search; `PlateStrip` visual signature (IBM Plex Mono, confidence colour underline)
- Cameras page: list + `AddCameraModal`
- Design tokens: ink/bone/signal/alert/confirm/steel palette; `plate-text` CSS class

**Benchmarking**
- `ml/benchmarks/synthetic/generate_test_video.py`: 90s dashcam video, 12 synthetic plates across 3 virtual lanes with perspective scaling; outputs `phase1_gt.json`
- `ml/benchmarks/eval_phase1.py`: queries Postgres for `plate_read` events, computes recall + on-time recall, exits 0 on pass
- `make generate-test-video`, `make benchmark`, `make migrate`, `make seed` targets

**Infra**
- mediamtx RTSP server (compose `dev` profile) loops `test.mp4` as `rtsp://mediamtx:8554/test`
- Observability stack: Prometheus + Grafana + Loki (compose `observability` profile)

### Acceptance criteria (Phase 1 gate)
- ≥ 90% of known plates detected within 2s of appearing in stream
- Verified by `make benchmark` against synthetic test video

## [0.0.0] — 2026-07-02

### Added
- Monorepo skeleton: `apps/`, `packages/`, `ml/`, `deploy/`, `docs/` layout
- Root `Makefile` with `dev`, `test`, `lint`, `build`, `licenses` targets
- `pnpm-workspace.yaml` and root `package.json` for JS workspaces
- `pyproject.toml` with `uv` workspace, `ruff`, `mypy`, `pytest` configuration
- Bare FastAPI service (`apps/api`) with `/health` endpoint
- Bare Django 5 admin app (`apps/admin`)
- Bare Celery worker app (`apps/worker`)
- Next.js 15 web app (`apps/web`) with TypeScript, Tailwind CSS, shadcn/ui
- Expo React Native mobile app stub (`apps/mobile`)
- `packages/shared-python`: Pydantic + SQLAlchemy canonical entity models
- `packages/ui`: design token package (colors, typography, spacing, radius)
- Docker Compose stack: postgres (PostGIS), redis, minio, api, admin, worker, web, nginx
- Alembic baseline migration for all canonical entities
- GitHub Actions CI: lint, typecheck, unit tests, Docker image builds
- GitHub Actions license check: fails on AGPL/GPL in prod dependencies
- `LICENSES.md` generator (`make licenses`)
- `CONTRIBUTING.md`, `SECURITY.md`, `README.md`
