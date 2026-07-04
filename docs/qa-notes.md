# DrishtiAI — QA Findings (Pre-Pilot Code Review)

**Reviewer:** Claude Code  
**Date:** 2026-07-04  
**Scope:** Full codebase walk — shared-python → api → admin → worker → pipeline → web → mobile → deploy → CI

---

## Summary

**6 blockers · 10 high · 10 medium · 7 low**

---

## BLOCKER

### B-01 — Route ordering bug makes `/cameras/live-status` and `/cameras/health-summary` unreachable

**File & line:** `apps/api/src/drishtiai_api/routers/cameras.py:160,190`

**Issue:** FastAPI matches routes in registration order. `GET /{camera_id}` is registered at line 106, before `GET /live-status` (line 160) and `GET /health-summary` (line 190). A request to `/cameras/live-status` hits the `/{camera_id}` handler first, which tries to parse `"live-status"` as a UUID and returns 422. The dashboard live-camera strip and health badge are therefore broken for all users.

**Proposed fix:** Move the literal-path routes (`/live-status`, `/health-summary`, `/discover`) to the top of the router, before any parameterised routes. FastAPI matches literals before path params when declared first.

---

### B-02 — UUID/string type mismatch in `_assert_site_access` blocks all site_admin webhook operations

**File & line:** `apps/api/src/drishtiai_api/routers/webhooks.py:97`

**Issue:** `_assert_site_access(current_user, site_id: uuid.UUID)` checks `if site_id not in (current_user.site_ids or [])`. `site_ids` is `ARRAY(String)` — a list of string UUIDs. `site_id` is a `uuid.UUID` object. `UUID("abc") not in ["abc"]` is always `True` in Python because UUID.__eq__ does not compare equal to plain strings. Result: every non-superadmin user gets 403 on all webhook endpoints for their own sites.

**Proposed fix:** Cast to string before comparison: `if str(site_id) not in (current_user.site_ids or [])`. Same type mismatch exists implicitly in `list_webhooks` at line 137 (`if site_id not in allowed`); fix there too.

---

### B-03 — SQL injection vector in `analytics.py` via unescaped timezone string

**File & line:** `apps/api/src/drishtiai_api/routers/analytics.py:72,137,168`

**Issue:** The site's timezone string (`_site_tz()` → `site.timezone`) is retrieved from the database and interpolated directly into raw SQL strings using f-strings:

```python
f"... AT TIME ZONE '{tz}' ..."
f"... INTERVAL '{days} days' ..."
```

`days` and `limit` are validated integers (safe). `tz` is a string from a DB column that any `site_admin` can set. A malicious value like `UTC'; DROP TABLE events; --` would execute. Even if current users are trusted, this pattern is dangerous and fails SAST scans.

**Proposed fix:** Use Postgres `SET timezone = ...` in a separate query or validate `tz` against `pytz.all_timezones` before interpolation. The `INTERVAL` literal can be replaced with a parameterised `AGE()` / `NOW() - :cutoff` pattern.

---

### B-04 — Refresh tokens not stored: no single-use rotation, no revocation

**File & line:** `apps/api/src/drishtiai_api/routers/auth.py:86`

**Issue:** `POST /auth/refresh` issues a new access + refresh token pair but never records the old refresh token as consumed. The old token remains valid until natural expiry (7 days). Consequences: (1) token theft is undetectable — a stolen refresh token works alongside the legitimate one indefinitely; (2) `POST /auth/logout` only revokes the current access token JTI via Redis denylist but the refresh token is still live; (3) "kick user" from admin cannot force a session end.

**Proposed fix:** Add a `refresh_token_hashes` table (columns: `jti`, `user_id`, `expires_at`, `revoked`). On issue, store `sha256(refresh_token)`. On use, verify the hash exists and is not revoked, then mark it revoked and issue a new token. On logout/password change, revoke all rows for the user.

---

### B-05 — Near-zero test coverage across the entire stack

**File & line:** `apps/api/tests/` (3 files), no tests elsewhere

**Issue:** Only 3 test files exist (`test_health.py`, `test_auth.py`, `test_cameras.py`) containing 5 test functions in total. Zero tests for: shared models, worker tasks (retention, reports, export, scheduled), pipeline (voter, alert_engine, parking_session, writer), admin, or any frontend component. Coverage is estimated at < 5% of production code paths. No unhappy-path tests (DB down, MinIO down, camera offline, invalid input) anywhere.

**Proposed fix:** Not a single-file fix — needs a testing sprint. Minimum acceptable before pilot: auth flows (login, refresh, logout, denylist), alert engine (exact/prefix/fuzzy match + no-match), voter consensus logic, parking session open/close, retention task dry-run, and webhook delivery. See PR 1 test plan.

---

### B-06 — No security CI gates

**File & line:** `.github/workflows/ci.yml` (entire file), `.github/workflows/security.yml` (missing)

**Issue:** CI runs lint, typecheck, pytest, and Docker builds. It does not run: Bandit (Python SAST), Semgrep (OWASP rulesets), pip-audit (dependency CVEs), pnpm audit (JS CVEs), gitleaks (secret scanning), CodeQL, or container scanning. Any of the BLOCKER findings above would have shipped through CI undetected.

**Proposed fix:** Add `.github/workflows/security.yml` per Part 2.6 of the hardening spec. Wire it as a required check on `master`. See PR 2 for the full implementation.

---

## HIGH

### H-01 — Login response reveals account state (403 vs 401)

**File & line:** `apps/api/src/drishtiai_api/routers/auth.py:52-56`

**Issue:** Wrong password / unknown user returns 401 with `"Incorrect email or password"`. Disabled account returns 403 with `"Account disabled"`. An attacker can enumerate valid accounts by observing the status code difference. The 403 path also skips the Argon2 hash computation, making timing-based enumeration even easier (5ms vs ~80ms response).

**Proposed fix:** Collapse all failure paths into a single 401 with body `{"error": {"code": "auth.invalid_credentials", "message": "Invalid credentials"}}`. Always run the Argon2 verify (even for unknown users, compare against a constant dummy hash) to equalise timing. Log the real reason server-side with the request ID.

---

### H-02 — Redis connection pool created and destroyed per HTTP request

**File & line:** `apps/api/src/drishtiai_api/deps.py:20-25`

**Issue:** `get_redis()` calls `aioredis.from_url(...)` on every request and `await r.aclose()` on teardown. This creates and tears down a full TCP connection pool for every single API call. Under any real load (>10 req/s) this will exhaust Redis connection limits and add ~5ms of overhead per request.

**Proposed fix:** Create the Redis pool once in FastAPI's lifespan context (`@asynccontextmanager`) and store it on `app.state.redis`. Yield it from `get_redis()` as `app.state.redis`. Closed only on application shutdown.

---

### H-03 — `POST /webhooks/{id}/test` blocks the event loop

**File & line:** `apps/api/src/drishtiai_api/routers/webhooks.py:238`

**Issue:** `_deliver(wh, body)` calls `urllib.request.urlopen(req, timeout=5)` — a synchronous blocking call — inside an `async def` endpoint without `asyncio.get_event_loop().run_in_executor()`. This blocks the entire event loop for up to 5 seconds per test call, starving all other in-flight requests.

**Proposed fix:** Replace `urllib` with `httpx.AsyncClient` (already an `httpx` transitive dep via FastAPI) and `await client.post(...)`, or wrap the urllib call in `run_in_executor`. Same issue exists in `gates.py:_fire_controller` called from `manual_trigger`.

---

### H-04 — No SSRF protection on webhook URLs or gate trigger URLs

**File & line:** `apps/api/src/drishtiai_api/routers/webhooks.py:115`, `apps/api/src/drishtiai_api/routers/gates.py:63,75`

**Issue:** Both webhook delivery and gate trigger make HTTP requests to URLs provided by the operator. No validation prevents URLs that resolve to RFC1918 addresses (10/8, 172.16/12, 192.168/16), loopback (127/8), or link-local (169.254/16). On a cloud-hosted deployment this is an SSRF vector for internal metadata endpoints (e.g. AWS IMDS at `169.254.169.254`).

**Proposed fix:** Before any HTTP dispatch to a user-configured URL, resolve the hostname and reject if the IP falls within private/reserved ranges. Re-check after each DNS resolution to defeat DNS rebinding. Implement as a `safe_fetch()` wrapper used by both webhooks and gates.

---

### H-05 — Argon2 parameters not explicitly set

**File & line:** `apps/api/src/drishtiai_api/auth/password.py:3`

**Issue:** `CryptContext(schemes=["argon2"])` uses passlib's default Argon2 parameters. Passlib 1.7.x defaults to `time_cost=2, memory_cost=102400, parallelism=8` (argon2id). The spec requires `time_cost=3, memory_cost=65536, parallelism=4`. Additionally, passlib wraps argon2-cffi without exposing explicit parameter validation, making it impossible to assert parameters in tests or detect if passlib changes defaults in a future version.

**Proposed fix:** Switch to `argon2-cffi` directly with explicit `PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)`. Wrap in `packages/shared-python/security/password.py` and import from there in both FastAPI and Django.

---

### H-06 — CORS allows all methods and headers

**File & line:** `apps/api/src/drishtiai_api/main.py:24-26`

**Issue:** `allow_methods=["*"]` and `allow_headers=["*"]`. This allows cross-origin `DELETE`, `PATCH`, and arbitrary custom headers from any origin listed in `cors_origins`. While `cors_origins` restricts origins, allowing all methods defeats part of the CORS contract.

**Proposed fix:** Restrict to `allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]` and `allow_headers=["Authorization", "Content-Type", "X-Request-ID"]`.

---

### H-07 — Django admin `ALLOWED_HOSTS` defaults to `["*"]`

**File & line:** `apps/admin/drishtiai_admin/settings.py:11`

**Issue:** `ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])`. When the env var is not set (e.g., first-run before `.env` is written), Django serves to any Host header, enabling Host header injection attacks. This also makes the admin misconfiguration invisible — no startup error occurs.

**Proposed fix:** Remove the default entirely: `ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")`. Django will raise `ImproperlyConfigured` if the variable is not set, forcing the installer to set it explicitly.

---

### H-08 — Gate ONVIF credentials stored as plaintext JSONB

**File & line:** `apps/api/src/drishtiai_api/routers/gates.py:81`, `packages/shared-python/src/drishtiai_shared/models/gate.py`

**Issue:** `GateControllerCreate.config: dict = {}` accepts arbitrary JSON including ONVIF `username`/`password` and webhook `secret` fields, which are stored in the `gate_controllers.config` JSONB column unencrypted. A DB read (backup leak, SQL injection, compromised replica) exposes all gate credentials.

**Proposed fix:** Credential fields within `config` must be encrypted at rest. Minimally, identify which keys are credentials (`password`, `secret`) and encrypt their values with Fernet before storing; decrypt on read. Better: separate a `credentials` column (encrypted) from non-sensitive `config`.

---

### H-09 — Push notifications sent to all users regardless of site

**File & line:** `apps/pipeline/src/drishtiai_pipeline/alert_engine.py:48-53`

**Issue:** `_send_push_notifications` scans `push_tokens:*` (all users across all sites/orgs) and delivers the alert push to every registered device. A guard at Site A (hotel) will receive push notifications from Site B (shopping mall). This is both a privacy issue and a UX blocker.

**Proposed fix:** Store push tokens scoped to site: key `push_tokens:{site_id}:{user_id}`. In `alert_engine.py`, only scan tokens for the matching `site_id`.

---

### H-10 — `total` count in paginated list endpoints ignores filters

**File & line:** `apps/api/src/drishtiai_api/routers/parking.py:136`, `apps/api/src/drishtiai_api/routers/visitor_passes.py:130`

**Issue:** Both endpoints return `total = db.scalar(select(func.count(Model.id)))` — a count of all rows in the table, not the filtered query. A site with 50 sessions will show `total: 8000` if there are 8000 sessions globally. Frontend pagination breaks.

**Proposed fix:** Apply the same filters to the count query: `db.scalar(select(func.count()).select_from(filtered_q.subquery()))`.

---

## MEDIUM

### M-01 — `datetime.utcnow()` (deprecated) used in report generation

**File & line:** `apps/worker/src/drishtiai_worker/tasks/reports.py:118`

**Issue:** `datetime.utcnow()` is deprecated since Python 3.12 and will be removed in a future version. It also returns a naive datetime, which can silently cause timezone bugs when mixed with timezone-aware datetimes elsewhere.

**Proposed fix:** Replace with `datetime.now(tz=timezone.utc)` throughout. Check the rest of the worker codebase for any other `utcnow()` calls.

---

### M-02 — Worker tasks create a new SQLAlchemy engine on every task invocation

**File & line:** `apps/worker/src/drishtiai_worker/tasks/retention.py:40-41`, `apps/worker/src/drishtiai_worker/tasks/reports.py:30-31`

**Issue:** Both `_engine()` functions call `create_engine(...)` on every task call. SQLAlchemy engines are expensive to create (they allocate a connection pool). Under Celery's process pool model, this creates a new engine per task, not per worker process.

**Proposed fix:** Create engines at module level (lazy, but initialised once per worker process):
```python
_engine = None
def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(...)
    return _engine
```

---

### M-03 — Visitor pass `single_use` flag never consumed by pipeline

**File & line:** `apps/pipeline/src/drishtiai_pipeline/parking_session.py`, `apps/pipeline/src/drishtiai_pipeline/alert_engine.py`

**Issue:** `VisitorPass.used` exists and `VisitorPass.single_use` is set on creation, but the pipeline never checks visitor passes on plate read and never marks a pass as `used=True`. A single-use visitor pass can be used unlimited times. The `pass_status` API also returns stale data as a result.

**Proposed fix:** In `parking_session.on_plate_read` (or `alert_engine.check_and_fire`), query for an active visitor pass matching the plate and site, and set `used=True` if `single_use=True`.

---

### M-04 — `/metrics` endpoint is unauthenticated

**File & line:** `apps/api/src/drishtiai_api/main.py:49`

**Issue:** `Instrumentator().expose(app, endpoint="/metrics", include_in_schema=False)` exposes Prometheus metrics without any authentication. In a deployment reachable from the internet or a shared network, this leaks internal service topology, request rates, error rates, and latency data.

**Proposed fix:** Either restrict `/metrics` to a separate internal port (configure `prometheus-fastapi-instrumentator` with `expose_port`), or add a `Bearer` token middleware that checks a static `METRICS_TOKEN` env var.

---

### M-05 — `update_user` audit log action is ambiguous for multi-field patches

**File & line:** `apps/api/src/drishtiai_api/routers/users.py:238`

**Issue:** `action = "user.activate" if body.is_active else (... "user.deactivate" ... else "user.update")`. If a PATCH changes `name` and sets `is_active=True`, the logged action is `"user.activate"` — the name change is invisible in the audit log. An auditor cannot reconstruct the full change history.

**Proposed fix:** Always log `"user.update"` for a PATCH that changes non-status fields, and additionally log `"user.activate"` or `"user.deactivate"` as a separate entry when `is_active` changes.

---

### M-06 — No OpenAPI descriptions or examples on most routes

**File & line:** Every router file

**Issue:** The majority of endpoints have no `summary`, `description`, or `responses` documentation beyond the `response_model`. FastAPI auto-generates names from function names, resulting in OpenAPI docs that show `List Cameras`, `Get Camera` etc. with no description of semantics, side effects, required roles, or error codes. This makes integration harder for mobile and third-party consumers.

**Proposed fix:** Add `summary=`, `description=`, and `responses={403: ..., 404: ...}` to `@router.get/post/patch/delete` decorators on all public-facing routes. At minimum, document auth requirements and error codes.

---

### M-07 — `StreamCapture.frames()` has no circuit breaker or shutdown check in inner loop

**File & line:** `apps/pipeline/src/drishtiai_pipeline/capture.py:41-55`

**Issue:** The inner while loop reads frames and reconnects on failure but never checks `_shutdown`. If the pipeline receives SIGTERM while in the inner loop waiting for frames, the thread can take up to `RECONNECT_DELAY` (5s) + frame-read timeout before unblocking. With `main.py`'s `t.join(timeout=10)`, a slow camera thread can prevent clean shutdown.

**Proposed fix:** Pass `shutdown_event` into `StreamCapture` and check `shutdown_event.is_set()` at the top of the inner while loop.

---

### M-08 — `cameras.py` has dead `db: DbSession = None` parameter in `live_status`

**File & line:** `apps/api/src/drishtiai_api/routers/cameras.py:165`

**Issue:** `async def live_status(..., db: DbSession = None)` — the `db` parameter is declared but never used (the route only queries Redis). The default `None` silently disables the DI-injected session, and mypy will flag this as a type error since `DbSession` is `Annotated[Session, Depends(...)]`.

**Proposed fix:** Remove the `db` parameter entirely from `live_status`.

---

### M-09 — Celery tasks have no retry bounds or `bind=True` pattern

**File & line:** `apps/worker/src/drishtiai_worker/tasks/retention.py:53`, `apps/worker/src/drishtiai_worker/tasks/reports.py:156`

**Issue:** Neither task uses `bind=True`, `max_retries`, or `autoretry_for`. A transient DB or MinIO failure causes a task to fail permanently with no retry. Beat will reschedule the next occurrence 24h later, meaning a single overnight DB hiccup skips a full day's retention enforcement.

**Proposed fix:** Add `@app.task(bind=True, max_retries=3, default_retry_delay=300, autoretry_for=(Exception,))` and handle retries inside the task body.

---

### M-10 — `hmac.new()` is a deprecated alias

**File & line:** `apps/api/src/drishtiai_api/routers/webhooks.py:102`, `apps/pipeline/src/drishtiai_pipeline/webhook_fire.py:66`

**Issue:** `hmac.new(secret.encode(), body, hashlib.sha256)` uses the deprecated `hmac.new()` alias. While functionally correct in Python 3.11, it may be removed in a future version and triggers deprecation warnings.

**Proposed fix:** Replace with `hmac.HMAC(secret.encode(), body, hashlib.sha256)` or the preferred pattern `hmac.new(...)` → `hmac.new(key, msg, digestmod)`. Actually the correct replacement is to use `hashlib.new('sha256')` style or just the `hmac.new(key, msg, digestmod)` call (which is still present in 3.12). The truly safe form is `hmac.HMAC(key=..., msg=..., digestmod=hashlib.sha256).hexdigest()`.

---

## LOW

### L-01 — `print()` calls in seed scripts are intentional but should use `logging`

**File & line:** `apps/api/scripts/seed_dev_data.py`, `apps/api/scripts/seed_superadmin.py`

**Issue:** Scripts use `print()` for output. Not a production-path issue, but log format is inconsistent with the rest of the stack and makes these scripts harder to integrate with automated installer logging.

**Proposed fix:** Replace `print()` with a simple `logging.info()` call; configure `basicConfig` at the top of each script.

---

### L-02 — No pagination on camera list

**File & line:** `apps/api/src/drishtiai_api/routers/cameras.py:66-75`

**Issue:** `GET /cameras` returns all cameras with no limit, cursor, or page parameter. An enterprise installation with 64 cameras is fine; 256 cameras starts to slow. No `ORDER BY` clause means results are non-deterministic.

**Proposed fix:** Add `ORDER BY cameras.created_at` and a `limit` parameter (default 100). For phase 1 this is low priority but should be tracked.

---

### L-03 — Missing `response_model` on several routes

**File & line:** `apps/api/src/drishtiai_api/routers/auth.py:99`, `apps/api/src/drishtiai_api/routers/cameras.py:136,149`, `apps/api/src/drishtiai_api/routers/analytics.py:63`

**Issue:** Some endpoints return `dict` without a `response_model`, bypassing Pydantic serialisation validation. This means extra fields from ORM objects could be included in responses unexpectedly.

**Proposed fix:** Add explicit `response_model=` to all endpoints that return structured data.

---

### L-04 — `capture.py` reconnect delay is a class constant, not configurable

**File & line:** `apps/pipeline/src/drishtiai_pipeline/capture.py:19`

**Issue:** `RECONNECT_DELAY = 5.0` is hardcoded. For enterprise deployments with flaky cameras, this may need tuning per camera.

**Proposed fix:** Accept an optional `reconnect_delay` constructor parameter, defaulting to the class constant.

---

### L-05 — No docstrings on Celery tasks

**File & line:** `apps/worker/src/drishtiai_worker/tasks/scheduled.py`

**Issue:** `run_daily_reports` and `run_retention_all_sites` have no docstrings. Per the task spec, each Celery task should document its purpose, inputs, retries, and side effects.

**Proposed fix:** Add task-level docstrings with: purpose, trigger (Beat schedule), inputs, outputs, side effects, retry behaviour.

---

### L-06 — Django admin has no app-specific admin customisations registered

**File & line:** `apps/admin/drishtiai_admin/apps/sites_app/admin.py`, `apps/admin/drishtiai_admin/apps/cameras_app/admin.py`

**Issue:** The two admin apps exist as stubs but expose default `ModelAdmin` with no list_display, search_fields, ordering, or readonly_fields. The Django admin currently shows raw UUIDs and offers no useful filtering. This is usable but will confuse operators.

**Proposed fix:** Add at minimum `list_display`, `list_filter`, `search_fields`, and `readonly_fields = ("created_at", "updated_at")` to each admin class.

---

### L-07 — `gst_capture.py` existence check — fallback path not tested

**File & line:** `apps/pipeline/src/drishtiai_pipeline/gst_capture.py`

**Issue:** `gst_capture.make_capture()` returns a GStreamer capture or falls back to `StreamCapture`. The fallback path is used in all non-GPU environments (including local dev and CI). There are no tests verifying the fallback works correctly or that the `make_capture` factory behaves as expected when GStreamer is unavailable.

**Proposed fix:** Add a unit test for `make_capture` with GStreamer mocked as unavailable, confirming `StreamCapture` is returned.

---

## Deferred (out of scope for this pass, log for follow-up)

| # | Finding |
|---|---|
| D-01 | MFA enrollment UI and TOTP enforcement for `superadmin`/`site_admin` — spec requires this but no User model field or enrollment flow exists |
| D-02 | OIDC adapter (`authlib`) for enterprise SSO — not present; requires `oauth_accounts` table migration |
| D-03 | `apps/site` marketing site — does not exist; full greenfield build |
| D-04 | Rate limiting (`slowapi`) — no rate limiting anywhere on auth endpoints |
| D-05 | Account lockout (progressive backoff after failed logins) — not implemented |
| D-06 | Webhook secret Fernet encryption at rest (KMS envelope) — currently stored plaintext |
| D-07 | `packages/ui/tokens.ts` design token package — does not exist |
| D-08 | Content Security Policy headers — not set anywhere in API or Next.js |
| D-09 | `axe-core` accessibility CI integration — not wired |
| D-10 | ONVIF camera discovery (`POST /cameras/discover` returns 501) |
| D-11 | Video clip storage and retrieval — `clip_key` exists on Event but pipeline never writes clips |
| D-12 | Continuous recording pipeline stage — referenced in RetentionPolicy `data_class` but never written |
