# Contributing to DrishtiAI

Thank you for considering a contribution. This document covers everything you need to get a change merged cleanly.

---

## Table of contents

- [Prerequisites](#prerequisites)
- [Development setup](#development-setup)
- [Branch and commit conventions](#branch-and-commit-conventions)
- [Pull request checklist](#pull-request-checklist)
- [Code style](#code-style)
- [Testing](#testing)
- [License hygiene](#license-hygiene)
- [Security](#security)
- [Architecture decisions](#architecture-decisions)

---

## Prerequisites

| Tool | Minimum version | Purpose |
|---|---|---|
| Docker Engine | 26.0 | Running the full stack |
| Docker Compose | v2.27 | Compose orchestration |
| Python | 3.12 | API, pipeline, worker |
| [`uv`](https://docs.astral.sh/uv/) | 0.4 | Python dependency management |
| Node.js | 20 LTS | Web and mobile frontends |
| pnpm | 9 | JS package management |
| Git | 2.40 | Version control |

---

## Development setup

```bash
# Clone
git clone https://github.com/emanthen/DrishtiAI.git
cd DrishtiAI

# Install all dependencies (Python + JS)
make install

# Copy and configure environment
cp .env.example .env
# Edit .env — at minimum set: POSTGRES_PASSWORD, MINIO_ROOT_PASSWORD,
#                              API_SECRET_KEY, DJANGO_SECRET_KEY

# Start infrastructure only (faster for API/web development)
make dev-infra

# In a second terminal: run the API in hot-reload mode
uv run uvicorn drishtiai_api.main:app --reload --app-dir apps/api/src

# Or start the full stack
make dev
```

Seed the database after first boot:

```bash
make migrate     # run Alembic migrations
make seed-dev    # create dev org, site, cameras, superadmin, test stream
```

---

## Branch and commit conventions

### Branches

```
feat/short-description          New feature
fix/short-description           Bug fix
chore/short-description         Dependency or tooling update
docs/short-description          Documentation only
refactor/short-description      Refactor without behavior change
```

### Commits — Conventional Commits

```
<type>(<scope>): <imperative subject, ≤72 chars>

[optional body]
[optional footer: Breaking-Change, Closes #123]
```

**Types:** `feat` · `fix` · `chore` · `docs` · `test` · `refactor` · `perf` · `ci`

**Scopes:** `api` · `pipeline` · `worker` · `web` · `mobile` · `admin` · `shared` · `deploy` · `ml`

Examples:

```
feat(api): add cursor-paginated audit log endpoint
fix(pipeline): handle dropped frames in analog RTSP ingest
chore(deps): update paddleocr to 2.9.1
docs(installer): add analog capture card FFmpeg command
perf(ocr): two-stage plate localisation — 5× throughput on CPU
```

Rules:
- One logical change per commit
- Subject is imperative mood ("add", not "added" or "adds")
- No period at end of subject line
- Breaking changes must include `BREAKING CHANGE:` in the footer

---

## Pull request checklist

Before requesting review, verify all of the following:

```
[ ] make lint       passes (ruff + mypy + eslint)
[ ] make typecheck  passes (mypy + tsc)
[ ] make test       passes (pytest + pnpm test)
[ ] make licenses   clean — no new AGPL/GPL in prod dependency graph
[ ] CHANGELOG.md    updated (new entry under [Unreleased])
[ ] .env.example    updated if new environment variables were added
[ ] Migration added if any SQLAlchemy model was changed
[ ] Phase acceptance criteria met (if closing a phase item)
[ ] No hardcoded secrets, hostnames, or absolute paths
[ ] No dead code or debug prints committed
```

PR description must include:
- **What** changed (one paragraph)
- **Why** it was needed
- **How to test** it manually

---

## Code style

### Python

```bash
uv run ruff check .        # lint
uv run ruff format .       # auto-format
uv run mypy apps packages  # type check
```

Key rules (enforced by `ruff`):
- PEP 8, line length 100
- No `from x import *`
- Type annotations required on all public functions
- No bare `except:` — always catch a specific type or at minimum `Exception`

### TypeScript / React

```bash
pnpm --recursive lint      # eslint
pnpm format                # prettier
pnpm --recursive typecheck # tsc --noEmit
```

Key rules:
- Strict TypeScript (`"strict": true`)
- No `any` type without an explanatory comment
- Components are named exports; no default exports from `lib/` modules
- `"use client"` only where needed — prefer Server Components

### SQL / Alembic

- Every schema change needs a new migration in `packages/shared-python/alembic/versions/`
- Migration files are numbered sequentially (`0001_`, `0002_`, …)
- Migrations must be reversible — always implement `downgrade()`
- Never issue `UPDATE` or `DELETE` against `audit_logs`

---

## Testing

```bash
make test              # all tests
make test-python       # Python only
make test-js           # JS/TS only

# Integration benchmarks (requires running stack)
make benchmark         # Phase 1 recall ≥ 90% within 2 s
make benchmark-11      # Phase 11 OCR precision ≥ 70%, CER ≤ 10%
```

### What to test

| Layer | What to cover |
|---|---|
| API routers | Happy path, auth errors (401/403), validation errors (422), not-found (404) |
| Pipeline | OCR normalization, voter consensus, watchlist matching |
| Worker tasks | Task returns expected shape; MinIO + DB interactions mocked |
| Web components | Render smoke tests; no `act()` warnings |

Do **not** mock the database for integration tests — use a real Postgres instance via `dev-infra`. We were bitten by mock/prod divergence before.

---

## License hygiene

**Rule:** No AGPL or GPL library may appear anywhere in the production dependency graph.

Before adding any new dependency:

1. Check the license on PyPI / npm.
2. Run `make licenses` after adding it.
3. If `make licenses` reports AGPL or GPL, remove the dependency, find an alternative, or get explicit written approval with an isolation strategy documented in `LICENSES.md`.

Allowed licenses (non-exhaustive): MIT, Apache 2.0, BSD-2, BSD-3, ISC, PSF, CC0.

---

## Security

- Never commit `.env` files, credentials, certificates, model weights, or anything with keys.
- If you accidentally commit a secret: rotate it immediately, force-push to remove the commit from history, and notify the team.
- All new API endpoints must be behind `CurrentUser` authentication unless they are intentionally public (document why).
- Security-relevant actions (auth, admin writes) must call `audit.log_action()` — see `apps/api/src/drishtiai_api/audit.py`.
- See [SECURITY.md](SECURITY.md) for the vulnerability reporting process.

---

## Architecture decisions

Before making a significant structural change, check `docs/architecture.md` for the existing design. If you need to deviate:

1. Open an issue labelled `architecture` to discuss the change before implementing.
2. Document the decision (what, why, alternatives considered) in `docs/architecture.md`.

Key invariants that must not be broken without discussion:

| Invariant | Reason |
|---|---|
| Pipeline cannot import from API | Prevents circular dependency; pipeline writes events, API reads them |
| `audit_logs` is append-only | Compliance and forensic integrity |
| No AGPL/GPL in prod | Commercial licensing constraint |
| All event queries must be time-bounded | `events` table is partitioned by month; unbounded queries miss partitions |
| Heartbeat key TTL is 30 s | Camera health dashboard relies on key expiry for offline detection |
