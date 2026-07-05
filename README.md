# DrishtiAI

**On-premises ANPR and video analytics platform for South Asian markets.**

Turns every camera on your site into a vehicle sensor — reading plates, logging vehicles, opening gates, flagging watchlist matches, and surfacing incidents — with every byte stored on your own hardware.

[![License: Proprietary](https://img.shields.io/badge/license-proprietary-blueviolet)](#license)
[![Python](https://img.shields.io/badge/python-3.12-blue)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-black)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)](https://fastapi.tiangolo.com)

---

## What it does

| Capability | Description |
|---|---|
| **ANPR** | Two-stage OCR: OpenCV plate localisation → PaddleOCR on crops; confidence-weighted multi-frame voter |
| **Nepali plate normalisation** | Province-code prefix detection, zero-padded canonical form, two-row motorcycle plate handling |
| **Vehicle intelligence** | Vehicle color and type classification; `/vehicles` search with plate/color/type filters |
| **Review queue** | Low-confidence detections routed to human review flywheel (`/review-queue`) |
| **Parking management** | Entry/exit session tracking, tiered tariff engine, NPR billing, manual close/waive |
| **Gate control** | Webhook and ONVIF relay drivers; per-camera rules (any plate / watchlist / visitor pass); license-gated |
| **Alert engine** | Exact, prefix, and fuzzy plate matching against categorised watchlists (blocked / VIP / resident…) |
| **Visitor passes** | Time-bounded passes with single-use enforcement; cancel = immediate gate lockout |
| **Investigation** | pg_trgm fuzzy plate search; per-plate timeline + per-camera sighting history |
| **User management** | Role hierarchy (superadmin → site_admin → manager → guard → resident → auditor); per-site scoping |
| **Reports & exports** | CSV and PDF reports via API; async large-export tasks via Celery |
| **Audit log** | Append-only `audit_logs` table; every auth and admin action recorded with actor, IP, and metadata |
| **Webhooks** | Outbound HTTP callbacks with HMAC-SHA256 signing for 7 event types |
| **Mobile app** | Expo React Native: live stats, alerts, visitor passes, push notifications |
| **Observability** | Prometheus + Grafana + Loki; auto-provisioned DrishtiAI Ops dashboard |
| **Licensing** | Ed25519 hardware-locked node-lock tokens; offline expiry; degrade-don't-brick gate safety; operator CLI |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  IP Cameras (RTSP)          Analog Cameras (V4L2 → FFmpeg RTSP)     │
└────────────────────┬──────────────────────────────────┬─────────────┘
                     │                                  │
                     ▼                                  ▼
           ┌─────────────────────────────────────────────────┐
           │          apps/pipeline  (GStreamer / OpenCV)     │
           │   Capture → Detect → OCR → Voter → Event write  │
           └───────────────────────┬─────────────────────────┘
                                   │  Redis pub/sub
          ┌──────────────────┬─────┴───────────────────────────┐
          │                  │                                  │
          ▼                  ▼                                  ▼
  ┌──────────────┐  ┌─────────────────┐              ┌──────────────────┐
  │  apps/api    │  │  apps/worker    │              │  apps/admin      │
  │  FastAPI     │  │  Celery + Beat  │              │  Django 5        │
  │  REST + WS   │  │  Reports        │              │  Superuser panel │
  └──────┬───────┘  │  Retention      │              └──────────────────┘
         │          │  Exports        │
         │          └─────────────────┘
  ┌──────┴──────────────────────────────────┐
  │           PostgreSQL 16 + PostGIS        │
  │           Redis 7  ·  MinIO              │
  └─────────────────────────────────────────┘
         │                        │
         ▼                        ▼
  ┌─────────────┐        ┌──────────────────┐
  │  apps/web   │        │  apps/mobile     │
  │  Next.js 15 │        │  Expo RN         │
  │  Dashboard  │        │  iOS / Android   │
  └─────────────┘        └──────────────────┘
```

All services run in Docker Compose behind NGINX. **Zero internet required** for core function.

---

## Repository layout

```
apps/
  api/          FastAPI service — REST, WebSocket, JWT auth
  admin/        Django 5 admin panel
  worker/       Celery workers + Beat scheduler
  pipeline/     GStreamer/OpenCV pipeline, OCR, voter, alert engine
  web/          Next.js 15 operator dashboard
  mobile/       Expo React Native mobile app
  licensing/    Operator CLI entry point (delegates to packages/licensing)
packages/
  shared-python/  SQLAlchemy models, Alembic migrations, shared config
  shared-ts/      TypeScript types shared between web + mobile
  ui/             Design tokens (colours, typography, spacing)
  licensing/      drishtiai-licensing: Ed25519 token, fingerprint, enforcement, clock guard
ml/
  benchmarks/   Synthetic test video generator, Phase 1 + Phase 11 evaluators
  models/       Model weights (gitignored), fine-tuning scripts
deploy/
  compose/      Docker Compose stack, NGINX, Prometheus, Grafana, mediamtx
  install/      Installer wizard and upgrade scripts
  backups/      Backup output directory
docs/           Architecture, installer guide, admin guide, API reference
```

---

## Quick start (development)

**Prerequisites:** Docker 26+, Docker Compose v2, Node.js 20+, pnpm 9+, Python 3.12+, [`uv`](https://docs.astral.sh/uv/)

```bash
# 1. Clone and install all dependencies
git clone https://github.com/emanthen/DrishtiAI.git
cd DrishtiAI
make install

# 2. Copy and edit environment variables
cp .env.example .env
# Edit .env — set POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD, API_SECRET_KEY, DJANGO_SECRET_KEY

# 3. Start the full stack
make dev
```

| Service | URL |
|---|---|
| Web dashboard | http://localhost:3000 |
| API + Swagger docs | http://localhost:8000/api/docs |
| Django admin | http://localhost:8001/admin |
| MinIO console | http://localhost:9001 |
| Grafana (observability profile) | http://localhost:3001 |

```bash
# Run database migrations and seed a superadmin user
make migrate
make seed

# For a full dev environment with a test camera stream:
make seed-dev           # creates org, site, cameras, test stream
make generate-test-video
make dev                # starts mediamtx RTSP server (dev profile)
```

---

## Makefile targets

```
make install            Install all Python and JS dependencies
make dev                Start full stack (build + up)
make dev-infra          Start only postgres, redis, minio
make migrate            Run Alembic migrations
make seed               Create superadmin user
make seed-dev           Full dev seed (org + site + cameras + tariff)
make generate-test-video  Build synthetic test video + ground truth JSON
make benchmark          Evaluate Phase 1 recall (≥90% within 2s)
make benchmark-11       Evaluate Phase 11 OCR quality (precision + CER)
make lint               Run ruff + mypy + eslint
make typecheck          Python mypy + TypeScript tsc
make test               All Python + JS tests
make build              Build all Docker images
make backup             pg_dump → deploy/backups/
make licenses           Generate LICENSES.md (check for AGPL/GPL)
make stop               docker compose down
make clean              Down + remove volumes (destructive)
```

---

## Environment variables

See [`.env.example`](.env.example) for the full annotated reference. Key variables:

| Variable | Required | Description |
|---|---|---|
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password |
| `API_SECRET_KEY` | Yes | 50-char random string for JWT signing |
| `DJANGO_SECRET_KEY` | Yes | 50-char random string for Django |
| `MINIO_ROOT_PASSWORD` | Yes | MinIO root password |
| `PIPELINE_OCR_USE_GPU` | No | Enable GPU inference for PaddleOCR (default: `false`) |
| `PIPELINE_OCR_TWO_STAGE` | No | Two-stage plate localisation (default: `true`) |
| `PIPELINE_CAPTURE_BACKEND` | No | `gstreamer` or `opencv` (default: `gstreamer`) |
| `GRAFANA_PASSWORD` | Yes | Grafana admin password. Generate with `make keygen`. `admin` is rejected at startup. |

---

## Running with observability

```bash
# Start Prometheus, Grafana, Loki, postgres-exporter, redis-exporter
docker compose -f deploy/compose/docker-compose.yml --profile observability up
```

The `DrishtiAI Ops` Grafana dashboard is provisioned automatically. Open http://localhost:3001. Log in with username `admin` and the `GRAFANA_PASSWORD` you set in `.env` (run `make keygen` to generate one).

---

## Running tests

```bash
make test               # all Python + JS tests
make test-python        # Python only (pytest)
make test-js            # JS/TS only (pnpm test)
make benchmark          # integration: recall against synthetic video
make benchmark-11       # integration: Phase 11 OCR quality metrics
```

---

## API reference

Interactive docs are available at `/api/docs` (Swagger UI) and `/api/redoc` (ReDoc) when the API service is running.

Core resource groups:

| Prefix | Description |
|---|---|
| `/auth` | Login, refresh, logout, me, TOTP MFA setup/verify |
| `/cameras` | Camera CRUD, live-status, health-summary |
| `/events` | Plate read events, snapshot/clip retrieval |
| `/plates` | pg_trgm fuzzy search, per-plate timeline, camera sightings |
| `/vehicles` | Vehicle search with plate/color/type filters |
| `/review-queue` | Low-confidence detection review; approve/reject |
| `/alerts` | Alert list, ack/snooze/resolve |
| `/watchlists` | Watchlist CRUD, plate entry management |
| `/parking-sessions` | Session lifecycle, tariff management |
| `/gates` | Controller CRUD, rule management, manual trigger |
| `/visitor-passes` | Pass CRUD, mine shorthand |
| `/users` | User CRUD, password reset |
| `/webhooks` | Outbound webhook registration, test ping |
| `/audit-logs` | Append-only audit trail |
| `/reports` | CSV + PDF report generation |
| `/analytics` | Stat cards, hourly/daily/occupancy charts, top plates |
| `/notifications` | Expo push token register/unregister |
| `/system/health` | Live system health (Postgres, Redis, MinIO, pipeline) |
| `/system/license` | Current license state, expiry banner data |
| `/metrics` | Prometheus metrics endpoint |

---

## Technology choices

| Concern | Choice | Rationale |
|---|---|---|
| Object detection | RT-DETR (Apache 2.0) | No AGPL/GPL exposure; production-grade accuracy |
| OCR | PaddleOCR (Apache 2.0) | Best accuracy for South Asian plate formats |
| Video capture | GStreamer + OpenCV | GStreamer for zero-copy GPU path; OpenCV fallback |
| Web framework | FastAPI + SQLAlchemy | Async, typed, Battle-tested |
| Database | PostgreSQL 16 + PostGIS | Time-partitioned events table; pg_trgm plate search |
| Object storage | MinIO | S3-compatible, fully on-premises |
| Task queue | Celery + Redis | Simple, reliable, no extra broker service |
| Frontend | Next.js 15 + Tailwind CSS | App Router, RSC, full TypeScript |
| Mobile | Expo (React Native) | Single codebase for iOS and Android |

**License constraint:** No AGPL or GPL libraries are permitted in the production dependency graph. Run `make licenses` before merging any dependency change.

---

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | Service map, data flow, database schema overview |
| [Installer guide](docs/installer-guide.md) | Production installation on Ubuntu 24.04, hardware sizing, upgrades |
| [Changelog](CHANGELOG.md) | Full version history |
| [Contributing](CONTRIBUTING.md) | Branching, commit style, PR checklist |
| [Security policy](SECURITY.md) | Vulnerability reporting, threat model, security defaults |

---

## License

Proprietary — all rights reserved. See [LICENSES.md](LICENSES.md) for third-party dependency licenses.

For commercial licensing enquiries contact **sales@drishtiai.com**.
