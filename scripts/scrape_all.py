#!/usr/bin/env python
"""Scrape all sources and seed opportunities into Postgres.

Usage:
    .venv/Scripts/python.exe scripts/scrape_all.py

Stores opportunities with NEUTRAL analysis (no user-specific scores).
Per-user scoring happens at request time in the API layer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("astra.scrape_all")


def main() -> None:
    from astra_scrapers.spiders.devpost_api import fetch_open_hackathons
    from astra_scrapers.types import ScrapedOpportunity

    all_scraped: list[ScrapedOpportunity] = []
    sources: dict[str, int] = {}

    # --- Devpost ---
    logger.info("Fetching from Devpost...")
    try:
        devpost = fetch_open_hackathons(max_pages=5)
        all_scraped.extend(devpost)
        sources["Devpost"] = len(devpost)
        logger.info("  Devpost: %d hackathons", len(devpost))
    except Exception as exc:
        logger.error("  Devpost failed: %s", exc)

    # --- MLH ---
    logger.info("Fetching from MLH...")
    try:
        from astra_scrapers.spiders.mlh_api import fetch_mlh_events
        mlh = fetch_mlh_events()
        all_scraped.extend(mlh)
        sources["MLH"] = len(mlh)
        logger.info("  MLH: %d events", len(mlh))
    except Exception as exc:
        logger.error("  MLH failed: %s", exc)

    # --- Unstop ---
    logger.info("Fetching from Unstop...")
    try:
        from astra_scrapers.spiders.unstop_api import fetch_unstop_opportunities
        unstop = fetch_unstop_opportunities(max_pages=3, opportunity_type="hackathon")
        all_scraped.extend(unstop)
        sources["Unstop"] = len(unstop)
        logger.info("  Unstop: %d", len(unstop))
    except Exception as exc:
        logger.error("  Unstop failed: %s", exc)

    # --- Hack2Skill ---
    logger.info("Fetching from Hack2Skill...")
    try:
        from astra_scrapers.spiders.hack2skill_api import fetch_hack2skill
        h2s = fetch_hack2skill()
        all_scraped.extend(h2s)
        sources["Hack2Skill"] = len(h2s)
        logger.info("  Hack2Skill: %d", len(h2s))
    except Exception as exc:
        logger.error("  Hack2Skill failed: %s", exc)

    # --- HackerEarth ---
    logger.info("Fetching from HackerEarth...")
    try:
        from astra_scrapers.spiders.hackerearth_api import fetch_hackerearth_events
        he = fetch_hackerearth_events()
        all_scraped.extend(he)
        sources["HackerEarth"] = len(he)
        logger.info("  HackerEarth: %d", len(he))
    except Exception as exc:
        logger.error("  HackerEarth failed: %s", exc)

    logger.info("Total scraped: %d from %d sources", len(all_scraped), len(sources))

    if not all_scraped:
        logger.warning("No opportunities scraped. Exiting.")
        return

    # --- Seed into Postgres (neutral — no user-specific enrichment) ---
    import asyncpg

    async def seed() -> int:
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
            except Exception as exc:
                logger.warning("  SKIP %s: %s", s.title[:40], exc)
        total = await conn.fetchval("SELECT count(*) FROM opportunities")
        await conn.close()
        return total

    total = asyncio.run(seed())
    logger.info("Seeded %d. Total in DB: %d. Sources: %s", len(all_scraped), total, sources)


if __name__ == "__main__":
    main()
