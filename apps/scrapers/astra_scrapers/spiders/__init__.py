"""Scrapers for individual hackathon sources.

Each spider exposes a `parse_*_html(html: str) -> ScrapedOpportunity` function
so the parser can be exercised against fixture HTML in unit tests, and a
higher-level `scrape_*` entry that knows how to fetch live pages (added later
when going beyond fixtures).
"""
