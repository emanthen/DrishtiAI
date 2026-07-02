# DrishtiAI Installer Guide

## Prerequisites

- Ubuntu 24.04 LTS
- NVIDIA GPU with driver ≥ 535 (for pipeline; CPU fallback available for dev)
- Docker Engine 26+ + Docker Compose v2
- 32 GB RAM minimum (SMB profile)
- Static LAN IP recommended

## Installation

```bash
# 1. Download the release bundle
curl -LO https://releases.drishtiai.com/v1.0.0/drishtiai-v1.0.0.tar.gz
tar -xzf drishtiai-v1.0.0.tar.gz
cd drishtiai-v1.0.0

# 2. Run the installer wizard
sudo bash deploy/install/install.sh
```

The wizard will:
- Detect hardware profile (SMB / Mid / Enterprise)
- Check GPU driver version
- Prompt for POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD, DJANGO_SECRET_KEY
- Set up .env (chmod 600)
- Initialize the database (Alembic migration)
- Start all services via Docker Compose
- Prompt you to assign camera roles (anpr_lane / parking / perimeter / general)

## Analog camera capture

For BNC-to-PCIe cards (V4L2 devices), wrap them with FFmpeg:

```bash
# Generic V4L2 capture card → internal RTSP stream
ffmpeg -f v4l2 -input_format mjpeg -video_size 1920x1080 -framerate 25 \
  -i /dev/video0 \
  -c:v libx264 -preset ultrafast -tune zerolatency \
  -f rtsp rtsp://localhost:8554/analog/cam0
```

Add the resulting RTSP URL as the camera stream URL in the admin panel.

## Storage sizing

```
GB per camera per day = (bitrate_Mbps × 3600 × 24) / 8000
Total = cameras × GB_per_camera × retention_days × redundancy_factor
```

Example: 30 cameras × 4 Mbps × 15 days continuous = ~1.94 TB.
Add 30% for event clips at higher retention ≈ 2.5 TB total.

## Upgrade

```bash
sudo bash deploy/install/upgrade.sh drishtiai-v1.1.0.tar.gz
```

This verifies the bundle signature, drains the pipeline, runs new migrations, and restarts services.
