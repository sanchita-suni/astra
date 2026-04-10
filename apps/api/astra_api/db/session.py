"""Async SQLAlchemy session factory.

Lazy-built so the API can boot and serve fixture data without a live database
(needed for Day 1 acceptance — Postgres isn't required to run `/opportunities/demo`).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from astra_api.settings import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    future=True,
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
