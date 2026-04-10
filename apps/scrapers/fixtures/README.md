# Scraper fixtures

Hand-saved HTML snapshots used to develop and test the Day 2 spiders without hammering live sites.

## Sources

- `devpost_*.html` — saved from `devpost.com/hackathons`
- `mlh_*.html` — saved from `mlh.io/seasons/2026/events`
- `unstop_*.html` — saved from `unstop.com/hackathons`

## How to refresh

Save raw HTML via your browser's "Save Page As → HTML Only" or `curl` (most pages render server-side enough to be parseable). The Day 2 spiders parse these locally first, then graduate to live targets once selectors are stable.
