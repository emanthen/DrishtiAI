# DrishtiAI — Architecture

## Contents

- [System overview](#system-overview)
- [Services](#services)
- [Data flow: plate read event](#data-flow-plate-read-event)
- [Data flow: gate trigger](#data-flow-gate-trigger)
- [Database schema overview](#database-schema-overview)
- [Redis key conventions](#redis-key-conventions)
- [Background jobs](#background-jobs)
- [Observability](#observability)
- [Key invariants](#key-invariants)

---

## System overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Physical layer                                  │
│   IP cameras (RTSP/H.264)          Analog cameras (V4L2 → FFmpeg RTSP) │
└──────────────────────┬──────────────────────────────────┬───────────────┘
                       │                                  │
                       ▼                                  ▼
         ┌─────────────────────────────────────────────────────┐
         │            apps/pipeline                            │
         │  GStreamer appsink  →  RT-DETR detect               │
         │  OpenCV candidates  →  PaddleOCR on crops           │
         │  Multi-frame voter  →  Plate consensus              │
         │  Alert engine       →  Watchlist match              │
         │  Gate evaluator     →  Controller trigger           │
         │  Parking session    →  Entry/exit lifecycle         │
         └──────────────────────┬──────────────────────────────┘
                                │
                   Redis pub/sub channels
                                │
          ┌───────────────────┬─┴───────────────────┐
          │                   │                     │
          ▼                   ▼                     ▼
  ┌──────────────┐   ┌─────────────────┐   ┌──────────────────┐
  │  apps/api    │   │  apps/worker    │   │  apps/admin      │
  │  FastAPI     │   │  Celery + Beat  │   │  Django 5        │
  │  REST + WS   │   │  Reports        │   │  Superuser ops   │
  │  Auth + RBAC │   │  Retention      │   └──────────────────┘
  │  Webhooks    │   │  Exports        │
  │  Audit log   │   └─────────────────┘
  └──────┬───────┘
         │
  ┌──────▼──────────────────────────┐
  │   PostgreSQL 16 + PostGIS       │
  │   Redis 7  ·  MinIO             │
  └─────────────────────────────────┘
         │                      │
         ▼                      ▼
  ┌─────────────┐      ┌────────────────┐
  │  apps/web   │      │  apps/mobile   │
  │  Next.js 15 │      │  Expo RN       │
  └─────────────┘      └────────────────┘
```

All services communicate over the Docker Compose internal network. NGINX is the only process that binds to a LAN-addressable port.

---

## Services

| Service | Framework | Internal port | Role |
|---|---|---|---|
| `api` | FastAPI 0.115 | 8000 | REST API, WebSocket hub, JWT auth, RBAC |
| `admin` | Django 5 | 8001 | Superuser admin panel |
| `worker` | Celery 5.4 | — | Background tasks (reports, retention, exports) |
| `beat` | Celery Beat | — | Cron scheduler (daily reports, nightly retention) |
| `pipeline` | GStreamer / OpenCV | — | Video ingest, OCR, alert engine, gate control |
| `web` | Next.js 15 | 3000 | Operator dashboard |
| `nginx` | NGINX alpine | 80 / 443 | Reverse proxy, TLS termination |
| `postgres` | PostgreSQL 16 + PostGIS | 5432 | Primary relational store |
| `redis` | Redis 7 alpine | 6379 | Task queue, pub/sub, token denylist, heartbeats |
| `minio` | MinIO latest | 9000 / 9001 | Object store (snapshots, clips, recordings, exports) |
| `mediamtx` | bluenviron/mediamtx | 8554 | RTSP relay for dev testing (`dev` profile only) |
| `prometheus` | prom/prometheus | 9090 | Metrics scrape + storage (`observability` profile) |
| `grafana` | grafana/grafana | 3001 | Dashboards (`observability` profile) |
| `loki` | grafana/loki | 3100 | Log aggregation (`observability` profile) |
| `postgres-exporter` | prometheuscommunity | 9187 | Postgres metrics for Prometheus |
| `redis-exporter` | oliver006 | 9121 | Redis metrics for Prometheus |

---

## Data flow: plate read event

```
1.  Camera frame arrives via GStreamer appsink (zero-copy where possible).
2.  Frame is sampled (1 of every PIPELINE_FRAME_SAMPLE frames).
3.  RT-DETR / OpenCV detects vehicle bounding boxes.
4.  For each vehicle:
    a. OpenCV Sobel + contour finds plate candidate crops.
    b. PaddleOCR runs on each crop (CLAHE + unsharp-mask pre-processing).
    c. Post-OCR character correction applies position-aware substitutions.
    d. Nepal plate normaliser converts to canonical format (e.g. BA 1 PA 0001).
5.  PlateVoter accumulates reads for PIPELINE_VOTER_WINDOW_S seconds.
    On vehicle exit (gap > PIPELINE_VOTER_EXIT_GAP_S), the voter emits the
    confidence-weighted consensus read.
6.  PlateDeduplicator suppresses repeated reads within PIPELINE_DEDUP_SECONDS.
7.  Plate row upserted in PostgreSQL (text, region, format_class).
8.  Event(kind=plate_read) written to partitioned `events` table.
9.  Snapshot JPEG uploaded to MinIO `snapshots` bucket.
10. Event published to Redis channel `drishti:{site_id}:events`.
11. FastAPI WebSocket consumers forward to connected browser clients.
12. Alert engine checks all active WatchlistEntry rows for the site
    (exact / prefix / fuzzy match).
13. On match: Alert row created → published to `drishti:{site_id}:alerts` →
    Expo push notifications fired → outbound webhooks fired.
14. Parking session manager checks camera role:
    - parking_entry → open ParkingSession, set Redis key parking:open:{site_id}:{plate}
    - parking_exit  → close session, compute tariff, delete Redis key.
15. Gate evaluator checks GateRule rows for the camera; fires matching controllers.
```

---

## Data flow: gate trigger

```
1.  Pipeline calls gate.evaluate_and_trigger(db, camera_id, plate_text, event_id).
2.  Rules loaded from DB (ordered by priority, enabled only).
3.  Each rule condition evaluated:
    - any_plate     → always true
    - watchlist_match → check WatchlistEntry rows
    - permit_valid  → check VisitorPass rows (time-bounded, single-use enforced)
4.  Matching controllers triggered in priority order:
    - webhook driver: stdlib urllib.request POST with optional X-Gate-Secret HMAC.
    - ONVIF driver:   raw SOAP SetRelayOutputState with WS-Security digest auth.
5.  GateTriggerLog row written (success, error string, latency_ms).
6.  Gate failure never propagates to pipeline — logged and swallowed.
```

---

## Database schema overview

All migrations live in `packages/shared-python/alembic/versions/`.

### Core tables

| Table | Partitioned | Description |
|---|---|---|
| `organizations` | No | Top-level tenant |
| `sites` | No | Physical location (org-scoped) |
| `cameras` | No | Camera record with role, stream URL, health_status |
| `plates` | No | Canonical plate text + metadata (upserted on read) |
| `events` | **Yes (monthly by `ts`)** | All pipeline events; `kind` discriminator |
| `alerts` | No | Watchlist match alerts; lifecycle: new → ack → snoozed → resolved |
| `watchlists` | No | Named groups with category |
| `watchlist_entries` | No | Per-plate patterns (exact / prefix / fuzzy) |
| `parking_sessions` | No | Open/closed sessions with duration and tariff |
| `tariffs` | No | Tiered charge rules (JSON) |
| `gate_controllers` | No | Relay endpoint config (webhook / ONVIF) |
| `gate_rules` | No | Camera → controller mapping with trigger condition |
| `gate_trigger_logs` | No | Immutable trigger audit trail |
| `visitor_passes` | No | Time-bounded plate permissions |
| `users` | No | Auth accounts with role and site_ids (ARRAY) |
| `retention_policies` | No | Per-site per-data-class retain_days |
| `audit_logs` | No | Append-only security audit trail |
| `webhooks` | No | Outbound webhook registrations |

### Events partitioning

The `events` table is partitioned by range on `ts` (one partition per month). This keeps index sizes manageable as event volumes grow. **All queries against `events` must include a `ts` filter** — otherwise Postgres scans all partitions.

Partition naming: `events_YYYY_MM` (created by the migration or on-the-fly by the partition trigger).

---

## Redis key conventions

| Key pattern | Type | TTL | Description |
|---|---|---|---|
| `token:deny:{jti}` | String | Access token expiry | JWT denylist entry |
| `camera:heartbeat:{camera_id}` | String (JSON) | 30 s | Pipeline heartbeat; absence = offline |
| `camera:{camera_id}:frames` | List (JPEG bytes) | — | MJPEG frame buffer for live view |
| `parking:open:{site_id}:{plate_norm}` | String | 24 h | Open parking session guard |
| `push_tokens:{user_id}` | Set | None | Expo push token registrations |
| `drishti:{site_id}:alerts` | Pub/Sub channel | — | Real-time alert feed |
| `drishti:{site_id}:events` | Pub/Sub channel | — | Real-time plate read feed |
| `drishti:{site_id}:parking` | Pub/Sub channel | — | Parking session open/close feed |
| `drishti:system:camera_events` | Pub/Sub channel | — | Camera online/offline transitions |

---

## Background jobs

Celery workers consume from three queues. Celery Beat dispatches two scheduled jobs.

| Queue | Tasks |
|---|---|
| `celery` (default) | `run_daily_reports`, `run_retention_all_sites` (Beat fan-out) |
| `reports` | `generate_daily_report`, `generate_monthly_report` |
| `retention` | `enforce_retention_policy` |
| `export` | `export_events_csv`, `export_parking_csv` |

### Beat schedule

| Job | Crontab | What it does |
|---|---|---|
| `daily-reports` | `0 30 * * *` (00:30 UTC) | Fan-out daily PDF for all active sites |
| `nightly-retention` | `0 2 * * *` (02:00 UTC) | Fan-out retention enforcement for all active sites |

### MinIO bucket layout

| Bucket | Contents |
|---|---|
| `snapshots` | Per-event plate crop JPEG files — `{site_id}/{camera_id}/{event_id}.jpg` |
| `clips` | Short video clips around events |
| `recordings` | Continuous recording segments |
| `exports` | CSV exports — `exports/{site_id}/events_{from}_{to}_{hex}.csv` |
| `exports` (reports) | PDF reports — `reports/{site_id}/{date}/daily_summary.pdf` |

---

## Observability

Start with `--profile observability`:

```
Prometheus (9090) ─── scrapes ──► api:8000/metrics  (fastapi-instrumentator)
                               ► postgres-exporter:9187
                               ► redis-exporter:9121
                               ► pipeline:9100/metrics  (future)

Grafana (3001) ─── reads Prometheus, Loki
   └── DrishtiAI Ops dashboard (provisioned from grafana/provisioning/)
         - API request rate, P95 latency, 5xx error rate
         - Postgres active connections
         - Redis memory usage
         - Camera heartbeat key count

Loki (3100) ─── receives Docker json-file logs via Promtail (future)
```

API metrics endpoint: `GET /metrics` — no authentication required (Prometheus scrapes without a token).

---

## Key invariants

These must not be broken without an architecture discussion:

| Invariant | Why |
|---|---|
| Pipeline does not import from `drishtiai_api` | Prevents circular dependency; pipeline is a write path, API is a read path |
| `audit_logs` is append-only | Compliance and forensic integrity |
| No AGPL or GPL libraries in the prod dependency graph | Commercial licensing |
| All `events` queries must be time-bounded | Partitioned table — unbounded query hits every partition |
| Camera heartbeat TTL is exactly 30 s | Dashboard uses key absence for offline detection; too long = stale state |
| Voter emits after exit gap, not on timer | Reduces duplicate commits when a vehicle is stationary |
| Gate failure is always swallowed | A relay error must not stop the pipeline for other events |
