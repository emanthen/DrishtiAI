# Security policy

## Supported versions

| Version | Supported |
|---|---|
| Latest (`master`) | Yes |
| All prior releases | No — upgrade to latest |

---

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Report privately to: **security@drishtiai.com**

Include:
- A clear description of the vulnerability and affected component
- Step-by-step reproduction instructions
- Potential impact and exploitability assessment
- Any suggested fix or mitigation

**Response timeline:**

| Stage | Target |
|---|---|
| Acknowledgement | Within 48 hours |
| Initial triage | Within 5 business days |
| Patch release (critical) | Within 14 days |
| Patch release (high/medium) | Within 30 days |
| Public disclosure | After patch is available + 14-day customer update window |

We follow responsible disclosure. Reporters who follow this process will be credited (unless they prefer anonymity).

---

## Threat model

### Trust boundaries

```
Internet / external network
    │
    │  (no inbound connections — LAN-only product)
    │
   NGINX (only public-facing process)
    │  TLS 1.2+ (self-signed cert issued by installer)
    │
    ├── FastAPI (8000)  — all requests require Bearer JWT
    ├── Next.js (3000)  — static + SSR, no direct DB access
    ├── Django (8001)   — superadmin only, separate secret key
    └── MinIO (9000/9001) — listens on 127.0.0.1 only
         │
         └── Docker internal network
              ├── PostgreSQL (5432 — 127.0.0.1 only)
              ├── Redis (6379 — 127.0.0.1 only)
              └── Pipeline (no inbound ports)
```

**DrishtiAI is a LAN-only product. It must not be exposed to the internet without an additional hardened reverse proxy, VPN, or network segmentation layer.**

### Authentication and authorisation

- **JWT tokens** — HS256 signed; access tokens expire in 15 minutes; refresh tokens expire in 7 days.
- **Token revocation** — JTI denylist stored in Redis; logout immediately invalidates the token.
- **Role hierarchy** — `superadmin > site_admin > manager > guard > resident > auditor`. All write operations enforce the caller's role and org/site scope.
- **Passwords** — Hashed with Argon2id (via `passlib`). Minimum entropy enforced on auto-generated passwords (16 chars from letters + digits + `!@#$%`).

### Data protection

- **Audit log** — `audit_logs` table is append-only. The application never issues `UPDATE` or `DELETE` against it. Logged actions include: auth events (with client IP), user lifecycle (create/update/deactivate/reset_password), and future extension points.
- **Data at rest** — The installer sets up LUKS full-disk encryption on the storage volume. MinIO data, PostgreSQL data, and Redis AOF files are all on this volume.
- **Secrets in `.env`** — The installer sets `chmod 600 .env`. Secrets are passed to containers as environment variables, never baked into images.
- **MinIO credentials** — Generated randomly on first install. The root credentials are only used by the installer to create the application-scoped access key.

### Gate relay security

- Gate trigger endpoints require a fresh authenticated session.
- Every trigger attempt (success or failure) is written to `gate_trigger_logs` — immutable audit trail.
- Webhook-based gate controllers support `X-Gate-Secret` HMAC validation on the receiving end.

### Outbound webhooks

- Webhook payloads are signed with `X-Drishti-Signature: sha256=<hmac>` using a per-endpoint secret.
- The secret is never returned in API responses after creation (`has_secret: bool` only).
- Signing uses HMAC-SHA256 with the UTF-8 encoded secret and raw request body — compatible with GitHub webhook verification libraries.

### No telemetry

DrishtiAI makes **no outbound network calls** except:
- Expo Push API (`exp.host`) — only if mobile push tokens are registered and alerts fire.
- Outbound webhooks — only to URLs explicitly configured by an admin.
- NTP (OS-level) — not managed by DrishtiAI.

No usage data, crash reports, or analytics are sent anywhere.

---

## Security defaults

| Control | Value |
|---|---|
| Password hashing | Argon2id |
| JWT signing | HS256, 50-char random key |
| TLS version | 1.2+ (NGINX) |
| Certificate | Installer-issued self-signed (swap for CA cert in production) |
| MinIO credentials | Random 32-char string generated at install |
| `.env` permissions | `chmod 600` |
| Redis auth | Not enabled by default; enable `requirepass` in `redis.conf` for multi-tenant environments |
| Postgres auth | Password auth (`md5`); restrict `pg_hba.conf` to Docker internal network |
| Audit retention | 365 days default; configurable via `retention_policies` table |

---

## Known limitations

- Redis does not require a password by default. In shared-infrastructure environments, set `requirepass` and update `REDIS_URL` accordingly.
- The self-signed TLS certificate will generate browser warnings. Replace with a proper CA certificate from your internal PKI or Let's Encrypt if the LAN has a domain.
- JWT refresh tokens are not currently tracked in the denylist — a stolen refresh token can be used until it expires (7 days). Force-expire by rotating `API_SECRET_KEY` (this invalidates all existing tokens).
