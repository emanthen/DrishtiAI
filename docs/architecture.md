# DrishtiAI Architecture

## Overview

DrishtiAI is a monorepo product with a layered architecture:

```
Cameras (IP RTSP + Analog V4L2)
    │
    ▼
GStreamer / DeepStream pipeline (apps/pipeline)
    │  Plate detect + OCR + vehicle attrs + tracking
    │
    ▼
Redis pub/sub (live events)
    │
    ├─► FastAPI (apps/api) ──► PostgreSQL 16 + PostGIS
    │       │                       │
    │       │                  MinIO (snapshots + clips)
    │       │
    │       ▼
    │   WebSocket ──► Next.js dashboard (apps/web)
    │               ──► Expo mobile app (apps/mobile)
    │
    └─► Celery workers (apps/worker)
            ├── Report generation
            ├── Retention enforcement
            └── Export jobs
```

## Services

| Service | Framework | Port | Purpose |
|---------|-----------|------|---------|
| `api` | FastAPI | 8000 | REST + WebSocket API, JWT auth |
| `admin` | Django 5 | 8001 | Admin panel, user management |
| `worker` | Celery | — | Background jobs |
| `pipeline` | GStreamer/DeepStream | — | Video + ML processing |
| `web` | Next.js 15 | 3000 | Operator dashboard |
| `nginx` | NGINX | 80/443 | Reverse proxy + TLS |
| `postgres` | PostgreSQL 16 + PostGIS | 5432 | Primary data store |
| `redis` | Redis 7 | 6379 | Queue, pub/sub, session cache |
| `minio` | MinIO | 9000 | Object storage (snapshots, clips) |

## Data flow: plate read event

1. Camera stream ingested via GStreamer (IP: RTSP; analog: FFmpeg→RTSP wrapper).
2. DeepStream detects vehicles per frame.
3. Plate detector localizes plate bounding box per vehicle.
4. Multi-frame voter aggregates OCR reads across the vehicle's tracker track.
5. Best-consensus read emitted; below-threshold reads go to review queue.
6. `Event(kind=plate_read)` written to Postgres; snapshot to MinIO.
7. Event published to Redis `drishti/{site_id}/events`.
8. FastAPI WebSocket consumers push to connected dashboard clients.
9. Alert engine checks watchlists; fires `Alert` if matched.
10. Notification dispatcher sends to configured channels.
