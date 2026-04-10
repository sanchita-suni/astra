"""Database layer — SQLAlchemy 2.0 async + asyncpg.

Day 1 keeps this minimal: a single `opportunities` table with a JSONB `digest`
column that stores the full Pydantic model. Schema normalization is deferred
until Day 4 (only fields we actually query/filter get promoted out of JSONB).
"""

from astra_api.db.models import Base, OpportunityRow
from astra_api.db.session import async_session, engine

__all__ = ["Base", "OpportunityRow", "async_session", "engine"]
