"""Prometheus counters for security-relevant events.

These are automatically included in the /metrics endpoint exposed by
prometheus-fastapi-instrumentator (it uses the global REGISTRY).
"""
from prometheus_client import Counter

auth_failures_total = Counter(
    "drishtiai_auth_failures_total",
    "Authentication failure events",
    ["reason"],  # labels: unknown_user | bad_password | account_inactive | locked | totp
)

account_lockouts_total = Counter(
    "drishtiai_account_lockouts_total",
    "Progressive account lockout events applied",
    ["level"],  # labels: 5min | 30min | 24h
)

totp_failures_total = Counter(
    "drishtiai_totp_failures_total",
    "TOTP verification failures",
)
