"""Registrations table — tracks which hackathons a user has registered for.

Revision ID: 0003_registrations
Revises: 0002_users
Create Date: 2026-04-10 20:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003_registrations"
down_revision: str = "0002_users"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "registrations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column("opportunity_id", sa.String(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_registrations_user_opp", "registrations", ["user_id", "opportunity_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_registrations_user_opp", table_name="registrations")
    op.drop_table("registrations")
