# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [0.14.0] — 2026-07-04

### Added — Phase 14: Audit logging + real system health probes

**Audit logging**
- `apps/api/src/drishtiai_api/audit.py` — `log_action(db, actor_id, action, target_type, target_id, ip, meta)` helper; adds to the DB session without committing so it participates in the surrounding transaction
- `routers/auth.py` — logs `user.login_success`, `user.login_failed` (with client IP via `Request`), and `user.logout`
- `routers/users.py` — logs `user.create`, `user.update`, `user.activate`, `user.deactivate`, `user.reset_password`
- `GET /audit-logs` — paginated, cursor-based; filterable by `action` (prefix), `actor_user_id`, `target_type`, `target_id`, time range; accessible to superadmin, site_admin, and auditor roles; results ordered newest-first
- Web dashboard `/audit` — table with time, action badge (colour-coded by severity), truncated actor UUID, target type+id, IP, meta JSON; filter form for action/actor/target; cursor-based "Load more" pagination

**System health probes** (`GET /system/health`)
- Postgres: `SELECT 1` through the existing DB session — confirms connectivity and migrations ran
- Redis: `await redis.ping()` — async PING through the existing aioredis client
- MinIO: `list_buckets()` via the existing Minio client (sync, run in executor) — confirms credentials and bucket access
- Pipeline: counts `camera:heartbeat:*` keys in Redis — reports how many cameras are currently reporting heartbeats
- Returns `{ok: bool, api, database, redis, minio, pipeline}` each with `{status, detail}`;  `ok` is false if any component is in error state
- Replaces the previous stub that returned `"unknown"` for all non-API components

## [0.13.0] — 2026-07-04

### Added — Phase 13: Celery Beat + outbound webhooks

**Celery Beat scheduler**
- `celery_app.py` — added `beat_schedule` config with two entries:
  - `daily-reports` — `crontab(hour=0, minute=30)` → `run_daily_reports`
  - `nightly-retention` — `crontab(hour=2, minute=0)` → `run_retention_all_sites`
- `tasks/scheduled.py` — fan-out tasks that query all active `sites` rows and dispatch per-site `generate_daily_report` / `enforce_retention_policy` tasks; Beat only needs one schedule entry per job type
- `beat` service added to Docker Compose (reuses the worker Dockerfile, runs `celery beat`); separate from the worker service so Beat can be scaled/restarted independently

**Outbound webhook integrations**
- `Webhook` SQLAlchemy model (`packages/shared-python`) — `site_id`, `name`, `url`, optional `secret` (HMAC-SHA256), `events` (Postgres ARRAY; empty = subscribe to all), `enabled`, `last_triggered_at`, `last_status_code`
- Migration `0003_webhooks.py` — creates `webhooks` table with `ix_webhooks_site_id` index
- `apps/pipeline/src/drishtiai_pipeline/webhook_fire.py` — `fire(db, site_id, event_type, payload)`: loads enabled webhooks, signs payload with `X-Drishti-Signature: sha256=…` (GitHub-style), POST via stdlib `urllib.request`; updates `last_triggered_at` + `last_status_code` per delivery; swallows exceptions
- `alert_engine.py` — calls `webhook_fire.fire(event_type="alert_new", …)` after committing alerts (best-effort, same pattern as push notifications)
- Supported event types: `plate_read`, `alert_new`, `alert_resolved`, `gate_trigger`, `camera_offline`, `parking_open`, `parking_close`

**API** (`GET|POST|PATCH|DELETE /webhooks`, `POST /webhooks/{id}/test`)
- Full CRUD — site_admin+ scoped to their sites; superadmin sees all
- `POST /webhooks/{id}/test` — sends a synthetic `{"event":"ping"}` payload to the URL, returns `{status_code, ok, error}`; records the attempt on the Webhook row
- `WebhookOut` schema hides the secret (returns `has_secret: bool` instead)
- Router mounted at `/webhooks` in `main.py`

**Web dashboard** (`/webhooks`)
- List of registered webhooks with name, URL, enabled/disabled badge, signed badge, subscribed event tags, last-triggered timestamp + HTTP status
- "+ Add webhook" inline form: name, site ID, URL, optional signing secret, event multi-select toggles
- Per-row: Test button (fires ping, shows HTTP result inline), Enable/Disable toggle, Delete

## [0.12.0] — 2026-07-04

### Added — Complete stack: worker tasks, observability, retention

**Worker tasks**
- `tasks/export.py` — `export_events_csv` / `export_parking_csv`: generate large CSV exports asynchronously, upload to MinIO `exports` bucket, return 24-hour presigned URL; handles up to 200 k / 100 k rows respectively
- `tasks/reports.py` — `generate_daily_report` / `generate_monthly_report`: full reportlab PDF (Traffic, Parking, Alerts, Top Plates, Hourly) generated in the Celery worker; stored under `reports/{site_id}/{date}/` in MinIO with 7-day presigned URL; eliminates potential API timeout on large PDF builds
- `tasks/retention.py` — `enforce_retention_policy(site_id)`: reads `retention_policies` table per site, hard-deletes expired `plate_read` events from Postgres, purges aged snapshots and clips from MinIO by object last-modified date; falls back to built-in defaults (plate events 90 d, snapshots 30 d, clips 14 d) when no policy row exists
- Added `reportlab>=4.2.0` to `apps/worker/pyproject.toml`

**API observability**
- `GET /metrics` — Prometheus exposition endpoint via `prometheus-fastapi-instrumentator` (MIT); exposes `http_requests_total`, `http_request_duration_seconds` histogram, and default process metrics; mounted without auth so Prometheus can scrape without a token
- Added `prometheus-fastapi-instrumentator>=7.0.0` to `apps/api/pyproject.toml`

**Docker Compose**
- `postgres-exporter` service (prometheuscommunity/postgres-exporter) added to `observability` profile; scrapes `DATA_SOURCE_NAME` from env; exposes `:9187`
- `redis-exporter` service (oliver006/redis_exporter) added to `observability` profile; scrapes `REDIS_ADDR`; exposes `:9121`
- Phase 11 OCR env vars added to `pipeline` service: `PIPELINE_OCR_USE_GPU`, `PIPELINE_OCR_TWO_STAGE`, `PIPELINE_OCR_PREPROCESS`

**Grafana dashboard**
- `deploy/compose/grafana/provisioning/dashboards/dashboards.yml` — file-provider config pointing at `/etc/grafana/provisioning/dashboards`
- `deploy/compose/grafana/provisioning/dashboards/drishtiai_ops.json` — `DrishtiAI Ops` dashboard (uid: `drishtiai-ops-v1`): API request rate, P95 latency, 5xx error rate, plate reads/min stat, Postgres connection count, Redis memory usage; auto-refreshes every 30 s; timezone set to `Asia/Kathmandu`

**Makefile**
- `benchmark-11` target: runs `ml/benchmarks/eval_phase11.py` against local Postgres (recall + precision + CER evaluation)

**Other**
- `deploy/backups/.gitkeep` — tracks the backup output directory in git so `make backup` has a destination
- `.env.example` — Phase 11 OCR vars documented with comments

## [0.11.0] — 2026-07-04

### Added — Phase 11: OCR pipeline improvements

**Two-stage plate localisation** (`ocr.py`)
- `_find_plate_candidates(frame)` — Sobel edge detection → horizontal dilation → contour filtering by aspect ratio (1.5–8.0) and area (≥ 800 px²); returns padded bounding boxes for candidate plate regions
- PaddleOCR now runs on each small crop instead of the full 1080p frame; typically 1–5 crops vs. one full-frame pass — 5–10× throughput improvement on CPU
- Falls back to full-frame OCR (with optional downscale to 1280 px wide) when no candidates are found, preserving existing behavior

**Crop pre-processing** (`ocr.py`)
- `_preprocess_crop(crop)` — (1) upscale if height < 32 px (PaddleOCR minimum), (2) CLAHE contrast enhancement (clip=2.0, 4×4 grid) for underexposed / night captures, (3) unsharp-mask sharpening (σ=2) to recover motion-blur lost detail
- Controlled by `PIPELINE_OCR_PREPROCESS=true` (default on)

**Post-OCR character correction** (`ocr.py`)
- `_correct_chars(text)` — position-aware substitution: leading alpha run gets digit→letter corrections (0→O, 1→I, 5→S, 2→Z, 6→G); trailing digit run gets letter→digit corrections (O→0, I→1, S→5, etc.); middle zone untouched to avoid false corrections
- `_normalize_np_plate(text)` — detects Nepal province-code prefixes (Ba/Ko/Ma/Ga/Lu/Ka/Su) and normalises to zero-padded canonical form (`BA1PA0001`), reducing watchlist mismatches caused by spacing/formatting differences

**Config** (`config.py`)
- `PIPELINE_OCR_USE_GPU` — passed directly to PaddleOCR; enables GPU inference without code change (previously hardcoded `False`)
- `PIPELINE_OCR_TWO_STAGE` — toggle two-stage localisation (default `True`)
- `PIPELINE_OCR_PREPROCESS` — toggle pre-processing pipeline (default `True`)

**Voter improvement** (`voter.py`)
- `_Track.consensus()` switched from pure majority vote to **confidence-weighted vote**: winner = text with highest cumulative confidence (sum of per-read confidence); reported confidence = average across winner reads
- Correctly handles the case where a high-confidence correct reading appears fewer times than a low-confidence OCR error
- Removed unused `Counter` import

**Benchmark** (`ml/benchmarks/eval_phase11.py`)
- Levenshtein-tolerant matching (≤ 1 char error accepted as a hit) for single-character substitution errors
- **Precision** metric: fraction of detected plates that are in ground truth (false positive rate)
- **CER** (Character Error Rate): avg Levenshtein / expected length per plate
- Acceptance criteria: `--min-precision` (default 0.70), `--max-cer` (default 0.10)
- False positive list printed at end of run
- Backwards-compatible with `phase1_gt.json` ground truth format

## [0.10.0] — 2026-07-04

### Added — Phase 10: Camera health monitoring

**Pipeline (`health.py`)**
- `SETEX camera:heartbeat:{id} 30 <json>` written every 10 s; TTL of 30 s means 3 missed heartbeats = key disappears; API reads this without subscribing to pub/sub
- JSON payload: `{camera_id, status, fps, frames, ts}` — fps calculated over the last report interval
- `drishti:system:camera_events` pub/sub channel receives a message on every status transition (online → offline, offline → online)
- `stop()` / `mark_offline()` methods: called from `process_camera` finally-block; deletes the heartbeat key immediately on clean shutdown so the dashboard reflects reality within seconds instead of waiting for TTL expiry; also sets DB `health_status = offline`

**API**
- `GET /cameras/live-status` — reads all `camera:heartbeat:*` Redis keys; returns `[{camera_id, online, fps, last_seen_s}]` for every camera that has reported within the last 30 s; polling-safe (no WS subscription needed)
- `GET /cameras/health-summary` — DB aggregate count `{online, offline, degraded, unknown, total}` by site; used by dashboard header

**Web dashboard — cameras page**
- Pulsing green dot (CSS `animate-ping`) for online cameras; solid red/grey for offline/unknown
- FPS column — live value from `/cameras/live-status` (5 s polling)
- "Last seen" column — seconds since last heartbeat
- Camera list auto-refreshes every 10 s via `refetchInterval`
- Offline count label under page title
- Role selector in "Add camera" modal now includes `parking_entry` / `parking_exit` options

**Web dashboard — layout**
- Red banner below the sidebar appears when any camera is offline: "N cameras offline — view cameras"; polls `/cameras/health-summary` every 30 s; disappears immediately when all cameras recover

## [0.9.0] — 2026-07-04

### Added — Phase 9: User management

**API** (`/users`)
- `GET /users` — list users scoped to caller's org; site_admin/manager see only users sharing at least one site; filterable by `role` and `is_active`
- `POST /users` — create user; auto-generates a 16-char password when none is provided; returns the plaintext password once (show-and-copy flow); site_admin can only assign roles below themselves (manager / guard / resident / auditor) and only to sites they belong to
- `GET /users/{id}` — fetch single user
- `PATCH /users/{id}` — update name, email, phone, role, site_ids, is_active (soft deactivate); same role-hierarchy rules enforced
- `DELETE /users/{id}` — soft-deactivate (sets `is_active = false`); cannot deactivate yourself
- `POST /users/{id}/set-password` — admin resets a user's password; auto-generates when body is empty; returns plaintext once
- Role hierarchy: superadmin > site_admin (can manage manager/guard/resident/auditor) > manager (read-only) 
- All write operations are scoped to the caller's `org_id`

**Web dashboard**
- `/users` page: sortable table with name, email, role badge (colour-coded by role), active/inactive badge, created date
- "+ Add user" form (inline, 2-column grid): name, email, role selector, phone, optional password
- Post-create banner shows the generated password until dismissed
- Per-row "Reset pwd" action — shows new auto-generated password in a dismissable banner
- Per-row "Deactivate / Activate" toggle (cannot deactivate yourself)
- Role and status filter dropdowns
- "Users" link added to sidebar (between Visitor passes and Reports)

## [0.8.0] — 2026-07-04

### Added — Phase 8: Export & reporting

**API** (`/reports`)
- `GET /reports/events.csv` — all events (plate reads, etc.) for a date range; columns: timestamp, kind, plate, camera, confidence, event_id; up to 50 000 rows
- `GET /reports/parking.csv` — parking sessions for a date range; columns: entry_time, exit_time, plate, duration_s, amount_NPR, payment_status, session_id
- `GET /reports/alerts.csv` — alerts for a date range; columns: timestamp, plate, watchlist, category, status, ack_at, notes, alert_id
- `GET /reports/daily-summary.pdf` — A4 PDF with five sections (Traffic overview · Parking · Alerts by status · Top 10 plates · Hourly traffic bar); built with `reportlab` (BSD licensed); lazy-imported so it doesn't slow server startup
- All endpoints accept `site_id`, `from`, `to` query params; default range is last 7 days; all queries are time-bounded to hit the partition index
- File download via `StreamingResponse` with `Content-Disposition: attachment`

**Web dashboard**
- `/reports` page with date-range pickers (from / to), three CSV download buttons, and a separate date picker for the PDF summary
- Downloads via `fetch` + `Blob` URL so the Bearer token is included (no token-in-URL exposure)
- "Reports" link added as last item in sidebar nav
- `API_BASE` exported from `lib/api.ts` for use by the download helper

**Dependencies**
- `reportlab>=4.2.0` added to `apps/api/pyproject.toml` (BSD licensed; lazy-imported only in the PDF route)

## [0.7.0] — 2026-07-04

### Added — Phase 7: Mobile app + push notifications

**Mobile app** (`apps/mobile`) — Expo Router v3 / React Native
- Login screen with email + password; JWT stored in `expo-secure-store`; auth-guard in root layout redirects unauthenticated users to login
- Bottom tab bar: Home · Passes · Alerts · Profile
- **Home** — 3×2 stat cards (events today, open alerts, active parking, revenue, gate triggers, active passes); recent 5 alerts list with plate tag, watchlist name, timestamp, status badge; pull-to-refresh
- **Visitor Passes** — tabbed by status (active / upcoming / expired / used); inline create form with plate, valid-from/to datetime pickers (pre-filled now → +24 h), single-use toggle, notes; cancel (hard-delete) with immediate gate lockout
- **Alerts** — tabbed by status (new / ack / snoozed / resolved); acknowledge and resolve actions with optimistic list removal; pull-to-refresh
- **Profile** — avatar initials, name, email, role badge; sign-out button that revokes JWT and deregisters push token
- `PlateTag` component — monospace, border-left accent, sm/md sizes
- `StatCard` component — surface card with coloured top border (default blue / alert red / confirm green)
- Zustand auth store with async `hydrateAuth` / `persistToken` / `clearToken` helpers for SecureStore
- Push token registered on tab mount via `expo-notifications`; unregistered on logout
- Metro monorepo config: `watchFolders` + `nodeModulesPaths` for workspace resolution

**API**
- `POST /notifications/register` — stores Expo push token in Redis SET `push_tokens:{user_id}`
- `POST /notifications/unregister` — removes token from the set

**Pipeline**
- `alert_engine.py`: after committing Alert rows, scans `push_tokens:*` Redis keys and fires Expo Push API (`exp.host`) via stdlib `urllib.request`; pure best-effort (exceptions swallowed, timeout 5 s); no new dependencies

## [0.6.0] — 2026-07-04

### Added — Phase 6: Analytics dashboard

**API** (`/analytics`)
- `GET /analytics/overview` — stat card data: events today, active parking sessions, revenue today, open alerts, gate triggers today, active visitor passes; uses site timezone for day boundary
- `GET /analytics/hourly-traffic?days=7` — plate-read count by hour-of-day (0–23), aggregated over last N days; all 24 hours always returned (zeros filled); uses `AT TIME ZONE` for local hour grouping
- `GET /analytics/daily-revenue?days=14` — daily parking revenue (NPR) + closed session count; zero-filled for days with no data
- `GET /analytics/occupancy` — entries and exits per hour over the last 24 h; drives area chart showing throughput trend
- `GET /analytics/top-plates?days=30&limit=10` — most-seen plate texts with read counts
- All queries are time-bounded to hit the `events` partition index

**Web dashboard**
- `/analytics` — site selector dropdown (multi-site users); Refresh button; all data fetched in a single `Promise.all`
- 6 stat cards: Events today · Active sessions · Revenue today · Open alerts · Gate triggers · Active passes (open alerts card highlights red when > 0)
- Hourly traffic bar chart (Recharts BarChart, last 7 days, hour labels)
- Daily revenue bar chart (revenue + sessions dual bars, last 14 days)
- Occupancy area chart (entries vs exits, last 24 h, gradient fill)
- Top plates horizontal bar chart (proportional bars, ranked 1–10)
- Analytics nav link added (second position in sidebar)

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
