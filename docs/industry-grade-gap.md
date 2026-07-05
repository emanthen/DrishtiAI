# DrishtiAI — Industry-Grade v1.0 Gap Assessment

**Date:** 2026-07-05
**Basis:** `master` @ `f794025`, verified by reading source files.
**Purpose:** Honest gap between current state and shipping a paid, production install.

Status legend: `absent` · `partial` · `present-needs-hardening` · `done`

---

## 1. Security Hardening

Target: pass the 5 requirements needed before any paid deal.

| Requirement | Status | Detail |
|---|---|---|
| Trusted auth — Argon2id / RS256 / MFA | **done** | Argon2id (t=3, m=64 MB, p=4) ✓; RS256 asymmetric JWT ✓; TOTP MFA ✓; tests assert specific parameter values |
| Generic auth errors | **done** | `auth.py` returns identical error for unknown email vs. wrong password; `test_security.py` asserts this |
| No plaintext secrets | **done** | `.env.example` uses `<generated-at-install>` for all sensitive vars; `GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_PASSWORD:?}` fails loudly if unset; gate credentials Fernet-encrypted at rest |
| Rate-limit + lockout | **done** | `lockout.py`: 5 attempts → 5 min, 10 → 30 min, 15+ → 60 min; per-IP slowapi rate limit on auth endpoints; tested in `test_security.py` |
| Input validation + SSRF protection | **present-needs-hardening** | Pydantic on all request bodies ✓; `http_safe.py` blocks RFC-1918 on webhook/gate URLs ✓; **gap:** no Bandit/Semgrep/Trivy in CI; no fuzz test for injection paths |
| **CI security gates** | **partial** | GitHub Actions runs lint + typecheck + unit tests; **missing:** SAST (Bandit), container scan (Trivy), secret scanning, dependency audit (pip-audit/pnpm audit) |

**Overall: present-needs-hardening** — auth/secrets hardening is solid. CI lacks automated security scanning.

**Blocker for paid deal?** The missing CI gates are not a runtime blocker; the code is sound. But a security-conscious enterprise buyer will want a scan report. Add `.github/workflows/security.yml` before the first commercial contract.

---

## 2. Licensing & Billing

| Requirement | Status | Detail |
|---|---|---|
| Node-lock (hardware binding) | **done** | Ed25519 + `FingerprintBundle` (motherboard/CPU/disk/MAC); 3-of-4 quorum matching |
| Offline expiry | **done** | Entire license term works without internet; renewal is the only connected operation |
| Degrade-don't-brick gate safety | **done** | `gate.evaluate_and_trigger()` checks `gate_automation_allowed()` before any pulse; hardware governs on expiry |
| License state machine | **done** | VALID/WARNING/GRACE/EXPIRED/HARDWARE_MISMATCH/INVALID; all tested |
| Clock-rollback guard | **done** | HMAC-SHA256 signed last-seen file; >120 s rollback raises `ClockTamperError`; tested |
| Operator CLI | **done** | `drishti-license issue/inspect/list/revoke`; SQLite billing DB at `~/.drishtiai/licenses.db` |
| Dashboard expiry banner | **done** | Amber (warning/grace) / red (expired/invalid) polling `/system/license` every 60 s |
| **Manual billing workflow** | **partial** | CLI + SQLite records invoices by reference number; **no invoice PDF generation, no Stripe/Esewa integration** |
| License server | **absent** | Issue/renew currently done from Prabhat's laptop; no multi-operator web UI for issuing tokens |
| Renewal flow for customer | **absent** | Customer has no self-service renewal; requires Prabhat to generate a new token and deliver it manually |

**Overall: present-needs-hardening** — the enforcement and gate-safety path is complete and tested. The billing/renewal workflow is manual-only, which is fine for the first 5–10 customers but will not scale.

---

## 3. Nepali OCR Specialisation

| Requirement | Status | Detail |
|---|---|---|
| Two-stage localisation | **done** | OpenCV plate candidate → PaddleOCR on crops; 5–10× throughput improvement |
| Crop pre-processing | **done** | CLAHE + unsharp-mask; configurable via env |
| Character correction (positional) | **done** | Leading alpha / trailing digit zone-aware substitutions |
| Nepal province-code normalisation | **done** | `_normalize_np_plate()` for all 7 province prefixes |
| Motorcycle two-row plate handling | **done** | Detected and merged in `ocr.py` |
| Confidence-weighted voter | **done** | Multi-frame vote on cumulative confidence sum |
| **Fine-tune on Devanagari / embossed dataset** | **absent** | Uses stock PaddleOCR weights; no Nepal-specific fine-tune |
| **Benchmark on real Nepali footage** | **absent** | `eval_phase1.py` runs on synthetic video only; no published recall/CER numbers on real plates |
| **Head-to-head vs Plate Recognizer** | **absent** | The key commercial claim ("beats foreign products on Nepali plates") is unproven |

**Overall: partial** — engineering pipeline is solid. The moat claim is unproven. This is the highest-leverage gap: a fine-tuned model with a published benchmark on real Nepali footage is what differentiates DrishtiAI from using Plate Recognizer.

**Critical path item** — must be proven before the first paid deal.

---

## 4. Vehicle Intelligence

| Requirement | Status | Detail |
|---|---|---|
| Vehicle type classification | **done** | Motorcycle/car/truck/bus/minibus enumeration; stored per vehicle |
| Vehicle color classification | **done** | 10-color palette; `COLOR_HEX` map; per-bar Cell in analytics chart |
| `/vehicles` search API | **done** | Filter by plate/color/type; `VehicleDetail` with plate list and sighting times |
| **Make / model detection** | **absent** | No model classifier; would require a separate detection head or API call |
| **Direction detection** | **absent** | Not implemented; relevant for wrong-way detection |
| **Appearance similarity search** | **absent** | No vector/embedding search across vehicle crops |

**Overall: partial** — color + type classification is done. Make/model and direction are absent. Appearance search (the "money shot" for investigation) is absent.

---

## 5. Beyond-ANPR Analytics

| Feature | Status | Detail |
|---|---|---|
| Stat cards (events/parking/alerts/gates) | **done** | 6 cards on analytics page |
| Hourly traffic chart | **done** | BarChart, last 7 days |
| Daily revenue chart | **done** | Dual bars (revenue + sessions), last 14 days |
| Occupancy area chart | **done** | Entries vs exits, last 24 h |
| Top plates chart | **done** | Ranked horizontal bar, last 30 days |
| Vehicle color + type charts | **done** | `Cell`-colored BarChart, dwell-time LineChart |
| Camera activity chart | **done** | Ranked by plate-read volume |
| **Zone editor** | **absent** | No spatial zone definition; no per-zone analytics |
| **Wrong-way detection** | **absent** | Requires direction + zone logic |
| **Illegal parking detection** | **absent** | No dwell-time threshold alert by zone |
| **Helmet detection** | **absent** | Would require a separate classifier |
| **Line counting** | **absent** | No virtual tripwire |
| **Camera tamper detection** | **absent** | No scene-change / blur / occlusion detection |

**Overall: partial** — standard ANPR analytics are solid. Video analytics (zone/wrong-way/helmet/tamper) are entirely absent.

---

## 6. Investigation

| Feature | Status | Detail |
|---|---|---|
| Plate text fuzzy search | **done** | pg_trgm trigram search scoped to site |
| Per-plate event timeline | **done** | Cursor-paginated; camera names; confidence; kind |
| Per-camera sighting summary | **done** | Read count + first/last seen per camera |
| `/investigate` dashboard page | **done** | Search → results → detail panel with tabs |
| **Camera map** | **absent** | No geospatial UI to see which cameras a vehicle passed |
| **Appearance search (crop similarity)** | **absent** | No vector search on vehicle images |
| **Multi-vehicle journey reconstruction** | **absent** | No automatic linking of a trip across cameras |

**Overall: partial** — plate-text investigation is done. Visual/geospatial investigation is absent. The "money shot" demo (show a vehicle's full journey across cameras on a map) is not yet buildable.

---

## 7. Scale

| Requirement | Status | Detail |
|---|---|---|
| Time-partitioned events table | **done** | Monthly partitions; `partition_manager.py` ensures ±3-month partitions at startup |
| pg_trgm plate search index | **done** | `ix_plates_text_trgm` on plate text |
| Redis pub/sub for live feeds | **done** | Events, alerts, parking, frames all via Redis channels |
| Multi-camera threading | **done** | One thread per camera; `_shutdown` event for clean stop |
| **Load test: 30–100 cameras** | **absent** | No benchmarked result at this scale; single-node threading approach may bottleneck |
| **DeepStream batching** | **absent** | GStreamer pipeline only; DeepStream batched-GPU path not started |
| **Horizontal pipeline scaling** | **absent** | No worker sharding; all cameras on one process |
| **Database connection pooling tuning** | **partial** | SQLAlchemy default pool; no documented sizing for 100-camera load |

**Overall: partial** — correct architecture for scale; not validated under load.

---

## 8. Reliability / Ops

| Requirement | Status | Detail |
|---|---|---|
| Docker Compose orchestration | **done** | All services; `restart: unless-stopped` on critical services |
| Database migrations at startup | **done** | `alembic upgrade head` in API entrypoint |
| `make backup` (pg_dump) | **partial** | Dump runs; output goes to `deploy/backups/`; **no automated restore test** |
| Health endpoint | **done** | `GET /system/health` checks Postgres, Redis, MinIO, pipeline heartbeats |
| **Installer wizard** | **absent** | `deploy/install/` is empty; no automated install script; no secret generation |
| **Backup restore round-trip test** | **absent** | No `make test-backup-restore` or CI job |
| **Pipeline watchdog** | **absent** | Docker `restart: unless-stopped` is the only recovery mechanism; no per-camera health monitor with auto-restart |
| **Upgrade path** | **absent** | No `make upgrade` or migration rollback tested procedure |
| **Alerting on service failure** | **absent** | Grafana dashboards exist; no alert rules configured |

**Overall: partial** — basic ops tooling is present. Installer wizard, restore round-trip, and watchdog are absent. These must exist before leaving a running system at a customer site unsupported.

---

## 9. UI Identity

| Requirement | Status | Detail |
|---|---|---|
| Design tokens (ink/bone/signal/alert/confirm) | **done** | `packages/ui/`, Tailwind config, dark mode |
| Shared component library | **done** | Button, Input, Select, ColorSwatch, KindChip, PageHeader, EmptyState |
| Plate strip visual (`PlateStrip`) | **done** | IBM Plex Mono; confidence underline colour coding |
| Dark mode | **done** | Tailwind `dark:` variants throughout; system preference |
| All 17 dashboard screens | **done** | Live view, analytics, events, investigate, vehicles, alerts, cameras, watchlists, review-queue, parking, gates, visitor-passes, users, webhooks, audit, reports, system |
| **Accessibility (WCAG 2.1 AA)** | **absent** | No `aria-label` audit; no keyboard-navigation test; no contrast-ratio check on signal/alert colours |
| **Responsive / mobile web** | **absent** | Dashboard is desktop-only; mobile users use the Expo app |

**Overall: present-needs-hardening** — visual identity is consistent and complete. Accessibility and responsive breakpoints are absent.

---

## 10. Demo / Proof

| Requirement | Status | Detail |
|---|---|---|
| Seeded demo environment | **done** | `make seed-dev`: 8 vehicles, 2 watchlists, 3 cameras, 300 events over 30 days; reproducible |
| Demo login credentials | **done** | `admin@drishtiai.local` / `devpassword123`; shown on login page |
| Smoke test | **done** | `tests/smoke_test.sh` — 12-endpoint curl test; exits 1 on any non-2xx |
| Synthetic test video | **done** | `generate_test_video.py` — 90s dashcam-style MP4, 12 plates, ground truth JSON |
| **Sales assets** | **absent** | No slide deck, one-pager, or recorded demo video |
| **Real pilot validation** | **absent** | No production install has run for 30 days; no client sign-off |
| **Published benchmark on real footage** | **absent** | Synthetic benchmark only; no peer-reviewable numbers |

**Overall: partial** — seeded demo is solid for technical evaluations. No commercial sales assets and no real-world pilot validation.

---

## Summary scorecard

| Area | Status | Blocking a paid deal? |
|---|---|---|
| Security hardening | present-needs-hardening | CI gates missing — low risk, add before first contract |
| Licensing & billing | present-needs-hardening | Core enforcement done; manual renewal only — acceptable for first 10 customers |
| Nepali OCR specialisation | **partial** | **Yes** — unproven moat; benchmark on real footage is required |
| Vehicle intelligence | partial | No — color/type done; make/model not critical yet |
| Beyond-ANPR analytics | partial | No — ANPR analytics are strong; zone/video-AI is future work |
| Investigation | partial | No — plate search is good enough for v1.0 demo |
| Scale | partial | No — architecture is right; load test before >10 cameras |
| Reliability / ops | **partial** | **Yes** — installer wizard + restore test required before leaving a system on-site |
| UI identity | present-needs-hardening | No — accessibility can follow after pilot |
| Demo / proof | partial | No — technical demo is ready; sales assets not needed to start pilot |

---

## Recommended immediate actions (before first paid install)

1. **Prove the Nepali OCR moat** — record 10 minutes of real Nepali plate footage; run `eval_phase11.py`; publish recall/CER numbers in `ml/benchmarks/nepali-ocr.md`; optionally run Plate Recognizer API on the same clips for a head-to-head table.
2. **Write the installer** — `deploy/install/install.sh`: clone repo, generate all secrets (`openssl rand -hex 32`), run `make migrate && make seed`, start services, print access credentials. Required before leaving a system at a customer site.
3. **Add CI security gates** — `.github/workflows/security.yml`: Bandit (Python SAST), Trivy (container scan), `pnpm audit`, `pip-audit`. Blocks PRs on HIGH+ findings.
4. **Backup restore round-trip test** — `make test-backup-restore`: `pg_dump` → destroy volume → `pg_restore` → assert row count. Run in CI nightly.
5. **End-to-end license gate test** — simulate EXPIRED state; assert `evaluate_and_trigger()` does not fire; assert dashboard shows red banner. Add to CI.
