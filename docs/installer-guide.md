# DrishtiAI — Installer guide

## Contents

- [System requirements](#system-requirements)
- [Hardware profiles](#hardware-profiles)
- [Storage sizing](#storage-sizing)
- [Installation](#installation)
- [Post-install configuration](#post-install-configuration)
- [Analog camera capture](#analog-camera-capture)
- [Connecting cameras](#connecting-cameras)
- [Upgrading](#upgrading)
- [Backup and restore](#backup-and-restore)
- [Uninstall](#uninstall)
- [Troubleshooting](#troubleshooting)

---

## System requirements

### Operating system

| Component | Requirement |
|---|---|
| OS | Ubuntu 24.04 LTS (x86_64) |
| Kernel | 6.8+ (ships with Ubuntu 24.04) |
| Docker Engine | 26.0+ |
| Docker Compose | v2.27+ |

### Minimum hardware (SMB profile — up to 8 cameras)

| Component | Minimum | Recommended |
|---|---|---|
| CPU | 8-core x86_64 (e.g. Intel i7-12700) | 16-core (Xeon or Ryzen 9) |
| RAM | 16 GB | 32 GB |
| GPU | None (CPU OCR fallback) | NVIDIA RTX 3060 or better |
| NVIDIA driver | — | ≥ 535 |
| System disk | 60 GB SSD | 120 GB NVMe |
| Storage volume | 500 GB | 2–4 TB (see sizing below) |
| Network | 1 GbE LAN | 2.5 GbE or 10 GbE for ≥ 16 cameras |

### GPU note

The pipeline runs PaddleOCR in CPU mode by default (`PIPELINE_OCR_USE_GPU=false`). To enable GPU:

1. Install NVIDIA driver ≥ 535 and CUDA 12.x.
2. Install the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).
3. Set `PIPELINE_OCR_USE_GPU=true` in `.env`.
4. Uncomment the `deploy.resources.reservations` block in `docker-compose.yml` for the `pipeline` service.

---

## Hardware profiles

| Profile | Cameras | RAM | GPU | Typical use case |
|---|---|---|---|---|
| SMB | 1–8 | 16 GB | Optional | Housing colony, small hotel |
| Mid | 9–24 | 32 GB | RTX 3060 | Mid-size hotel, shopping mall |
| Enterprise | 25–64 | 64 GB | RTX 4090 / A4000 | Large mall, corporate campus |

For more than 64 cameras, run multiple pipeline instances with different `PIPELINE_CAMERA_IDS` assignments.

---

## Storage sizing

Calculate required storage before installation:

```
Snapshots (JPEG) = cameras × events_per_day × avg_snapshot_kb / 1024 / 1024  GB/day

Clips (H.264)    = cameras × clips_per_day × avg_clip_duration_s × bitrate_Mbps / 8 / 1000  GB/day

Total = (snapshots + clips) × retention_days × 1.2 (20% overhead)
```

**Rule of thumb for housing colony (5–15 cameras, 200 reads/camera/day):**

| Retention | Storage |
|---|---|
| 7 days | 50–100 GB |
| 30 days | 200–400 GB |
| 90 days | 600 GB – 1.2 TB |

**Rule of thumb for busy mall (30 cameras, 2000 reads/camera/day):**

| Retention | Storage |
|---|---|
| 7 days | 300–600 GB |
| 30 days | 1.2–2.5 TB |
| 90 days | 3.5–7.5 TB |

---

## Installation

### 1. Prepare the host

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker Engine (Ubuntu instructions)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version          # should be ≥ 26.0
docker compose version    # should be ≥ 2.27
```

### 2. Download the release bundle

```bash
curl -LO https://releases.drishtiai.com/v0.14.0/drishtiai-v0.14.0.tar.gz
tar -xzf drishtiai-v0.14.0.tar.gz
cd drishtiai-v0.14.0
```

### 3. Run the installer wizard

```bash
sudo bash deploy/install/install.sh
```

The wizard will:

1. Detect your hardware profile (SMB / Mid / Enterprise)
2. Check GPU driver version (optional)
3. Prompt for required secrets:
   - `POSTGRES_PASSWORD` — choose a strong password (20+ chars)
   - `MINIO_ROOT_PASSWORD` — choose a strong password (20+ chars)
   - `API_SECRET_KEY` — 50-char random string (wizard generates one)
   - `DJANGO_SECRET_KEY` — 50-char random string (wizard generates one)
4. Write `.env` with `chmod 600`
5. Pull all Docker images
6. Run Alembic database migrations
7. Start all services via `docker compose up -d`
8. Seed a superadmin account (prompts for email + password)
9. Print the access URLs

### 4. Verify the installation

```bash
# Check all services are healthy
docker compose -f deploy/compose/docker-compose.yml ps

# Check API health
curl http://localhost:8000/health

# Check system health (all components)
curl http://localhost:8000/system/health
```

All components should show `"status": "ok"`.

Open the web dashboard at **http://\<server-LAN-IP\>** and log in with the superadmin credentials you set in step 3.

---

## Post-install configuration

### 1. Create your organisation and site

Log in to the Django admin at `http://<server>:8001/admin` with the superadmin credentials and create:

1. An **Organisation** record (your company name)
2. A **Site** record for each physical location (housing colony, hotel wing, etc.) with the correct timezone

Or use the FastAPI admin endpoint:

```bash
# Create org (superadmin token required)
curl -X POST http://localhost:8000/orgs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "My Company", "slug": "my-company"}'
```

### 2. Add cameras

In the web dashboard → Cameras → + Add camera:

| Field | Example | Notes |
|---|---|---|
| Name | Gate 1 Entry | Display name |
| Stream URL | `rtsp://192.168.1.100:554/stream1` | Camera RTSP URL |
| Role | `parking_entry` | See roles below |
| Site | My Site | Assign to a site |

**Camera roles:**

| Role | Description |
|---|---|
| `anpr_lane` | General plate reading, alert engine active |
| `parking_entry` | Opens a parking session on plate read |
| `parking_exit` | Closes the matching parking session |
| `perimeter` | Perimeter monitoring — events logged, no parking |
| `general` | General purpose — events only |

### 3. Configure retention policies

Default retention (applied when no policy row exists):

| Data class | Default |
|---|---|
| Plate events (DB rows) | 90 days |
| Snapshots (MinIO) | 30 days |
| Video clips (MinIO) | 14 days |
| Audit logs (DB rows) | 365 days |

Override per site via the API:

```bash
curl -X POST http://localhost:8000/retention-policies \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"site_id": "<uuid>", "data_class": "snapshots", "retain_days": 60}'
```

### 4. Configure tariffs (if using parking)

In the web dashboard → Parking → Tariffs → + Add tariff:

```json
{
  "grace_minutes": 10,
  "tiers": [
    { "up_to_minutes": 60,  "charge": 30 },
    { "per_hour": 30, "max_per_day": 300 }
  ]
}
```

---

## Analog camera capture

Analog cameras (BNC, CVBS) connected via a V4L2 capture card need an FFmpeg wrapper to produce an RTSP stream:

```bash
# Install FFmpeg
sudo apt install ffmpeg -y

# Basic V4L2 → RTSP (single channel)
ffmpeg \
  -f v4l2 -input_format mjpeg -video_size 1920x1080 -framerate 25 \
  -i /dev/video0 \
  -c:v libx264 -preset ultrafast -tune zerolatency -g 25 \
  -f rtsp rtsp://localhost:8554/analog/cam0 \
  2>> /var/log/drishtiai/analog-cam0.log &

# For a 4-channel DVR card (channels on /dev/video0..3)
for i in 0 1 2 3; do
  ffmpeg -f v4l2 -i /dev/video$i \
    -c:v libx264 -preset ultrafast -tune zerolatency \
    -f rtsp rtsp://localhost:8554/analog/cam$i &
done
```

Then add `rtsp://localhost:8554/analog/cam0` as the stream URL in the camera record.

Create a systemd unit to restart on boot:

```ini
# /etc/systemd/system/drishtiai-analog-cam0.service
[Unit]
Description=DrishtiAI analog capture cam0
After=network.target

[Service]
ExecStart=/usr/bin/ffmpeg -f v4l2 -input_format mjpeg -video_size 1920x1080 \
  -framerate 25 -i /dev/video0 -c:v libx264 -preset ultrafast \
  -tune zerolatency -g 25 -f rtsp rtsp://localhost:8554/analog/cam0
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now drishtiai-analog-cam0
```

---

## Connecting cameras

### IP camera checklist

- Set a **static IP** on the camera (or reserve via DHCP by MAC address).
- Enable **RTSP** on the camera (usually under Video → Streaming or Network → RTSP).
- Note the full RTSP URL format. Common patterns:

| Brand | URL pattern |
|---|---|
| Hikvision | `rtsp://<user>:<pass>@<ip>:554/Streaming/Channels/101` |
| Dahua | `rtsp://<user>:<pass>@<ip>:554/cam/realmonitor?channel=1&subtype=0` |
| Reolink | `rtsp://<user>:<pass>@<ip>:554/h264Preview_01_main` |
| Generic ONVIF | Use an ONVIF device manager to find the RTSP URL |

- Test the stream before adding it to DrishtiAI:

```bash
ffplay "rtsp://<user>:<pass>@<ip>:554/..." -vf "scale=640:-1"
```

### Recommended camera placement for ANPR

- Mount at 2.5–3.5 m height, angled 15–25° downward.
- Plate should occupy ≥ 15% of the frame width at the read point.
- Avoid strong backlight (position camera facing away from sunrise/sunset direction).
- Use IR-equipped cameras for overnight operation.
- Minimum resolution: 2 MP (1920×1080); 4 MP recommended for multi-lane coverage.

---

## Upgrading

```bash
# Download the new bundle
curl -LO https://releases.drishtiai.com/v<NEW>/drishtiai-v<NEW>.tar.gz

# Run the upgrade script (verifies signature, drains pipeline, migrates, restarts)
sudo bash deploy/install/upgrade.sh drishtiai-v<NEW>.tar.gz
```

The upgrade script:
1. Verifies the bundle GPG signature
2. Sends `SIGTERM` to the pipeline service (graceful drain — completes current events)
3. Pulls new Docker images
4. Runs `alembic upgrade head` for any new migrations
5. Restarts all services with zero downtime (rolling restart via Compose)
6. Prints a post-upgrade health check

**Never run `docker compose down -v`** during an upgrade — this destroys all data volumes.

---

## Backup and restore

### Backup

```bash
# Full database backup (runs inside the postgres container)
make backup
# Output: deploy/backups/postgres_YYYYMMDD_HHMMSS.sql

# MinIO backup (sync to external storage)
docker run --rm --net=host \
  -e MC_HOST_local="http://drishtiai:<minio_pass>@localhost:9000" \
  minio/mc mirror local/ /mnt/backup/minio/
```

Automate with cron:

```bash
# /etc/cron.d/drishtiai-backup
30 3 * * * root cd /opt/drishtiai && make backup >> /var/log/drishtiai/backup.log 2>&1
```

### Restore

```bash
# 1. Stop the API and worker (keep postgres running)
docker compose stop api worker beat

# 2. Restore database
cat deploy/backups/postgres_<timestamp>.sql | \
  docker compose exec -T postgres psql -U drishtiai drishtiai

# 3. Restart services
docker compose start api worker beat
```

---

## Uninstall

```bash
# Stop and remove containers + volumes (DESTRUCTIVE — all data lost)
docker compose -f deploy/compose/docker-compose.yml down -v --remove-orphans

# Remove images
docker image prune -a

# Remove the installation directory
sudo rm -rf /opt/drishtiai
```

---

## Troubleshooting

### Camera shows offline immediately

```bash
# Check pipeline logs
docker compose logs pipeline --tail=50

# Verify RTSP stream is reachable from the pipeline container
docker compose exec pipeline \
  ffprobe -v error -show_streams rtsp://<user>:<pass>@<ip>:554/...
```

### Plates not being read

1. Check pipeline logs for OCR errors.
2. Verify `PIPELINE_OCR_TWO_STAGE=true` — check pipeline logs for "no plate candidates found" (this triggers full-frame OCR fallback).
3. Test OCR on a still frame:
   ```bash
   docker compose exec pipeline python -c "
   from drishtiai_pipeline.ocr import detect_plates
   import cv2
   frame = cv2.imread('/tmp/test_frame.jpg')
   print(detect_plates(frame))
   "
   ```
4. Run the OCR benchmark against a test video: `make benchmark-11`.

### Celery tasks not running

```bash
# Check worker logs
docker compose logs worker --tail=50

# Check Beat logs (Beat dispatches scheduled tasks)
docker compose logs beat --tail=50

# Inspect Celery queue depth in Redis
docker compose exec redis redis-cli llen celery
```

### MinIO unreachable

```bash
# Check MinIO health
curl http://localhost:9000/minio/health/live

# Check MinIO logs
docker compose logs minio --tail=30

# Re-initialize buckets if they were deleted
docker compose restart minio-init
```

### Out of disk space

```bash
# Check disk usage
df -h /var/lib/docker

# Check MinIO data size
docker compose exec minio du -sh /data/

# Force immediate retention enforcement for all sites
docker compose exec worker celery -A drishtiai_worker.celery_app call \
  drishtiai_worker.tasks.scheduled.run_retention_all_sites
```
