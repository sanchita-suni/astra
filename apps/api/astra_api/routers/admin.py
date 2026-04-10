"""Admin endpoints — scrape trigger, DB stats, auto-refresh."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from astra_api.db import repository
from astra_api.deps import get_session

logger = logging.getLogger("astra.api.admin")

router = APIRouter(prefix="/admin", tags=["admin"])

# Track last scrape time for auto-refresh
_last_scrape: datetime | None = None


def _run_scrape_sync() -> dict:
    """Scrape all sources and seed neutral opportunities into Postgres."""
    from astra_scrapers.types import ScrapedOpportunity

    all_scraped: list[ScrapedOpportunity] = []
    sources: dict[str, int] = {}

    # Devpost
    try:
        from astra_scrapers.spiders.devpost_api import fetch_open_hackathons
        devpost = fetch_open_hackathons(max_pages=5)
        all_scraped.extend(devpost)
        sources["Devpost"] = len(devpost)
    except Exception as exc:
        sources["Devpost"] = 0
        logger.warning("Devpost failed: %s", exc)

    # MLH
    try:
        from astra_scrapers.spiders.mlh_api import fetch_mlh_events
        mlh = fetch_mlh_events()
        all_scraped.extend(mlh)
        sources["MLH"] = len(mlh)
    except Exception as exc:
        sources["MLH"] = 0
        logger.warning("MLH failed: %s", exc)

    # HackerEarth
    try:
        from astra_scrapers.spiders.hackerearth_api import fetch_hackerearth_events
        he = fetch_hackerearth_events()
        all_scraped.extend(he)
        sources["HackerEarth"] = len(he)
    except Exception as exc:
        sources["HackerEarth"] = 0
        logger.warning("HackerEarth failed: %s", exc)

    # Hack2Skill
    try:
        from astra_scrapers.spiders.hack2skill_api import fetch_hack2skill
        h2s = fetch_hack2skill()
        all_scraped.extend(h2s)
        sources["Hack2Skill"] = len(h2s)
    except Exception as exc:
        sources["Hack2Skill"] = 0
        logger.warning("Hack2Skill failed: %s", exc)

    # Seed into Postgres — neutral (no user-specific enrichment)
    import asyncpg

    async def _seed() -> int:
        conn = await asyncpg.connect(
            user="postgres", password="postgres",
            database="astra", host="localhost", port=5432,
        )
        count = 0
        for s in all_scraped:
            try:
                opp = s.to_stub_opportunity()
                digest = json.loads(opp.model_dump_json())
                await conn.execute(
                    "INSERT INTO opportunities (opportunity_id, digest, created_at, updated_at) "
                    "VALUES ($1, $2, NOW(), NOW()) "
                    "ON CONFLICT (opportunity_id) DO UPDATE SET digest = $2, updated_at = NOW()",
                    opp.opportunity_id, json.dumps(digest),
                )
                count += 1
            except Exception:
                pass
        total = await conn.fetchval("SELECT count(*) FROM opportunities")
        await conn.close()
        return total

    import asyncio as aio
    loop = aio.new_event_loop()
    total = loop.run_until_complete(_seed())
    loop.close()

    return {
        "scraped": len(all_scraped),
        "sources": sources,
        "total_in_db": total,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/scrape")
async def trigger_scrape() -> dict:
    """Trigger a fresh scrape of all sources and seed into DB.

    Sources: Devpost, MLH, HackerEarth, Hack2Skill.
    Opportunities are stored neutrally — per-user scoring happens at read time.
    """
    global _last_scrape
    result = await asyncio.to_thread(_run_scrape_sync)
    _last_scrape = datetime.now(timezone.utc)
    return result


@router.get("/stats")
async def db_stats(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """DB stats + last scrape time."""
    try:
        opps = await repository.list_opportunities(session, limit=1000)
        sources: dict[str, int] = {}
        types: dict[str, int] = {}
        for opp in opps:
            src = opp.metadata.source
            sources[src] = sources.get(src, 0) + 1
            t = opp.metadata.type
            types[t] = types.get(t, 0) + 1
        return {
            "total_opportunities": len(opps),
            "by_source": sources,
            "by_type": types,
            "last_scrape": _last_scrape.isoformat() if _last_scrape else None,
        }
    except Exception as exc:
        return {"error": str(exc)}


@router.post("/send-digest")
async def send_weekly_digest(
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Send a personalized digest email to all users with emails.

    Scores opportunities per-user and sends the top 10 best-fit ones.
    Call this from a cron job (weekly) or manually from Swagger.
    """
    from sqlalchemy import select

    from astra_api.db.models import UserRow
    from astra_api.db.user_repository import _to_profile
    from astra_api.email import build_digest_email, send_email_async
    from astra_core.feed_ranker import rank_opportunities

    # Get all users with emails
    result = await session.execute(
        select(UserRow).where(UserRow.email.isnot(None))
    )
    users = result.scalars().all()

    # Get all opportunities
    opps = await repository.list_opportunities(session, limit=200)

    sent = 0
    failed = 0
    for user_row in users:
        if not user_row.email:
            continue
        try:
            profile = _to_profile(user_row)
            ranked = rank_opportunities(
                opps,
                github_languages=None,
                resume=profile.resume,
                questionnaire=profile.questionnaire,
            )
            top_opps = [opp for opp, _ in ranked[:10]]
            html = build_digest_email(profile, top_opps)
            await send_email_async(
                user_row.email,
                "Your Weekly Hackathon Digest — Astra",
                html,
            )
            sent += 1
        except Exception as exc:
            logger.warning("Digest failed for %s: %s", user_row.github_login, exc)
            failed += 1

    return {"sent": sent, "failed": failed, "total_users": len(users)}
