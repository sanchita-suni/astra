"""SQLAlchemy ORM models.

Day 1 schema is deliberately dumb: one table, one JSONB column. We promote
fields out of JSONB only when we need to index, filter, or join on them
(scheduled for Day 4 once the analyst crew is producing real data).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OpportunityRow(Base):
    __tablename__ = "opportunities"

    opportunity_id: Mapped[str] = mapped_column(String, primary_key=True)
    digest: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class RegistrationRow(Base):
    __tablename__ = "registrations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    opportunity_id: Mapped[str] = mapped_column(String, nullable=False)
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class UserRow(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    github_login: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    github_name: Mapped[str | None] = mapped_column(String, nullable=True)
    github_avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    questionnaire: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resume: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resume_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
