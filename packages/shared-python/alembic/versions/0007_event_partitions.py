"""Create monthly event partitions

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-05
"""
from typing import Sequence, Union
from datetime import date

from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _bounds(year: int, month: int) -> tuple[str, str]:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start.isoformat(), end.isoformat()


def _offset(year: int, month: int, delta: int) -> tuple[int, int]:
    month += delta
    while month <= 0:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def upgrade() -> None:
    today = date.today()
    # Backfill 2 months, current, proactive 3 months ahead
    for delta in range(-2, 4):
        y, m = _offset(today.year, today.month, delta)
        start, end = _bounds(y, m)
        name = f"events_{y}_{m:02d}"
        op.execute(
            f"CREATE TABLE IF NOT EXISTS {name} "
            f"PARTITION OF events FOR VALUES FROM ('{start}') TO ('{end}')"
        )


def downgrade() -> None:
    today = date.today()
    for delta in range(-2, 4):
        y, m = _offset(today.year, today.month, delta)
        op.execute(f"DROP TABLE IF EXISTS events_{y}_{m:02d}")
