"""Initial schema — opportunities table.

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-10 12:00:00

The Day 1 contract is "one row per opportunity, with the entire validated
Opportunity Digest stored as JSONB." We deliberately do NOT explode fields out
into normalized columns yet — we add a GIN index on `digest` so we can still
query into it efficiently when Day 4 needs filters (e.g., by source or type).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "opportunities",
        sa.Column("opportunity_id", sa.String(), primary_key=True, nullable=False),
        sa.Column("digest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # GIN index lets us cheaply filter into the JSONB blob (e.g., by source,
    # type, or raw_requirements) before any normalization happens.
    op.create_index(
        "ix_opportunities_digest_gin",
        "opportunities",
        ["digest"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_opportunities_digest_gin", table_name="opportunities")
    op.drop_table("opportunities")
