"""add_anomaly_unique_constraint

Adds a unique constraint on (candle_time, ticker) in the anomalies table.
This prevents duplicate anomaly rows for the same candle on Celery task retry,
replacing the V1 comment "a unique constraint would prevent this in V2".

The detection task catches IntegrityError and logs the duplicate without failing.

Revision ID: c3d4e5f6a789
Revises: b2c3d4e5f678
Create Date: 2026-05-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "c3d4e5f6a789"
down_revision: Union[str, None] = "b2c3d4e5f678"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_anomaly_candle_time_ticker",
        "anomalies",
        ["candle_time", "ticker"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_anomaly_candle_time_ticker",
        "anomalies",
        type_="unique",
    )
