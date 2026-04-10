"""Users table for auth, questionnaire, and resume storage.

Revision ID: 0002_users
Revises: 0001_initial
Create Date: 2026-04-10 18:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_users"
down_revision: str = "0001_initial"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("user_id", sa.String(), primary_key=True, nullable=False),
        sa.Column("github_login", sa.String(), unique=True, nullable=False),
        sa.Column("github_name", sa.String(), nullable=True),
        sa.Column("github_avatar_url", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("questionnaire", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resume", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resume_filename", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_github_login", "users", ["github_login"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_github_login", table_name="users")
    op.drop_table("users")
