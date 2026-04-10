"""CRUD for the `opportunities` table.

The DB row is intentionally dumb: one JSONB column holding the validated
`Opportunity` model. This file is the only place that knows how to lift
between `Opportunity` (Pydantic) and `OpportunityRow` (SQLAlchemy) — every
other module touches Pydantic models only.

Upserts use Postgres `INSERT ... ON CONFLICT (opportunity_id) DO UPDATE` so
re-scraping the same opportunity doesn't churn rows or break references.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from astra_api.db.models import OpportunityRow
from astra_schemas import Opportunity


def _to_jsonable(opp: Opportunity) -> dict[str, Any]:
    """Pydantic → JSON-safe dict (datetimes/HttpUrls become strings)."""
    return json.loads(opp.model_dump_json())


async def upsert_opportunity(session: AsyncSession, opp: Opportunity) -> OpportunityRow:
    """Insert or update a single opportunity by `opportunity_id`.

    Updates `updated_at` server-side on conflict so freshness is queryable
    without parsing the JSONB blob.
    """
    payload = _to_jsonable(opp)
    now = datetime.now(timezone.utc)

    stmt = (
        pg_insert(OpportunityRow)
        .values(opportunity_id=opp.opportunity_id, digest=payload, updated_at=now)
        .on_conflict_do_update(
            index_elements=[OpportunityRow.opportunity_id],
            set_={"digest": payload, "updated_at": now},
        )
        .returning(OpportunityRow)
    )
    result = await session.execute(stmt)
    row = result.scalar_one()
    await session.commit()
    return row


async def get_opportunity_by_id(
    session: AsyncSession, opportunity_id: str
) -> Opportunity | None:
    """Fetch one row by ID and re-validate it through the Pydantic schema.

    Re-validation is intentional — if a stored row no longer matches the
    contract, we want a loud failure (500) rather than a silently bad payload.
    """
    stmt = select(OpportunityRow).where(OpportunityRow.opportunity_id == opportunity_id)
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return Opportunity.model_validate(row.digest)


async def list_opportunities(
    session: AsyncSession, *, limit: int = 200
) -> list[Opportunity]:
    """List opportunities, most recently updated first.

    Scoring/sorting is done per-user at the router layer, not here.
    """
    stmt = (
        select(OpportunityRow)
        .order_by(OpportunityRow.updated_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [Opportunity.model_validate(r.digest) for r in rows]
