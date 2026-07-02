# Security policy

## Reporting a vulnerability

Report security vulnerabilities privately to **security@drishtiai.com**. Do not open a public issue.

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any proposed fix

You will receive acknowledgement within 48 hours. We aim to release a fix within 14 days for critical issues.

## Threat model (summary)

Full threat model in `docs/threat-model.md` (generated at v1.0).

Key trust boundaries:
- **NGINX** is the only public-facing entry point. All services listen on `localhost` or the Docker internal network.
- **JWT tokens** are short-lived (15 min access, 7 day refresh) and revocable via Redis denylist.
- **Secrets** are loaded from `.env` (chmod 600), never hardcoded.
- **Audit log** (`AuditLog` table) is append-only; no UPDATE/DELETE is ever issued against it.
- **Data at rest** is encrypted via LUKS on the storage volume (installer step).
- **Gate trigger** requires a fresh authenticated session; the relay endpoint is audit-logged on every call.

## Security defaults

- Passwords hashed with Argon2id.
- HTTPS-only on LAN via installer-issued self-signed certificate.
- JWT signing keys (RS256) rotated on every upgrade.
- MinIO credentials are randomly generated on first install.
- No telemetry or external network calls from the core product.
