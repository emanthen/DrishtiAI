# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

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
