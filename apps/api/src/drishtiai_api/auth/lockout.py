"""Progressive account lockout backed by Redis.

Thresholds: 5 failures → 5-min lock, 10 → 30-min, 20 → 24-h.
Never a permanent/hard lock — prevents DoS on legitimate users.
Counters reset on successful login.
"""
from __future__ import annotations

import redis.asyncio as aioredis
from drishtiai_api.metrics import account_lockouts_total

# (min_failures, lock_duration_seconds) — most severe first
_THRESHOLDS: list[tuple[int, int, str]] = [
    (20, 86400, "24h"),    # ≥20 → 24 h
    (10, 1800,  "30min"),  # ≥10 → 30 min
    (5,  300,   "5min"),   # ≥5  → 5 min
]


async def is_locked(redis: aioredis.Redis, user_id: str) -> bool:
    return bool(await redis.exists(f"auth:lock:{user_id}"))


async def on_login_failure(redis: aioredis.Redis, user_id: str) -> None:
    """Record a failure and apply the appropriate progressive lock."""
    fail_key = f"auth:fail:{user_id}"
    count = await redis.incr(fail_key)
    if count == 1:
        await redis.expire(fail_key, 86400)  # 24-h window for fail counter

    for min_fails, lock_secs, label in _THRESHOLDS:
        if count >= min_fails:
            await redis.setex(f"auth:lock:{user_id}", lock_secs, "1")
            account_lockouts_total.labels(level=label).inc()
            return  # apply most severe matching lock, stop


async def on_login_success(redis: aioredis.Redis, user_id: str) -> None:
    await redis.delete(f"auth:fail:{user_id}", f"auth:lock:{user_id}")
