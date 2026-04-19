"""fix_server_defaults

Add DB-level server_default to iqr_flag and report_status so rows inserted
without explicitly specifying those columns get sensible defaults.

Revision ID: b2c3d4e5f678
Revises: e46dd1165378
Create Date: 2026-04-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f678"
down_revision: Union[str, None] = "e46dd1165378"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "anomalies",
        "iqr_flag",
        existing_type=sa.Boolean(),
        server_default="false",
        existing_nullable=False,
    )
    op.alter_column(
        "anomalies",
        "report_status",
        existing_type=sa.Enum("pending", "completed", "failed", name="reportstatus"),
        server_default="pending",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "anomalies",
        "report_status",
        existing_type=sa.Enum("pending", "completed", "failed", name="reportstatus"),
        server_default=None,
        existing_nullable=False,
    )
    op.alter_column(
        "anomalies",
        "iqr_flag",
        existing_type=sa.Boolean(),
        server_default=None,
        existing_nullable=False,
    )
