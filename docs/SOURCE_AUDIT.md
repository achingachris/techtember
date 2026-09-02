# Techtember source audit

**Audited:** 2 September 2026  
**Method:** Firecrawl map for URL coverage, then an attempted representative scrape per source. The map cap was 100 URLs; this was a fit check, not a full content crawl.

## Recommended initial set

| Source | Mapped URLs | Representative result | Fit | Operating strategy |
|---|---:|---|---|---|
| Techmeme | 99 | Map works, but URLs are mostly dated snapshots/fragments | Medium | Scrape the current front page only |
| TechCrunch | 100 | Cloudflare verification page | Low for direct crawl | Use search/RSS; keep configured crawl disabled |
| The Verge `/tech` | 97 | Clean technology listing, about 48 KB | High | Bounded crawl of `/tech/*` |
| Ars Technica | 100 | Clean AI listing with article links, about 27 KB | High | Crawl selected technology sections |
| Hacker News | 100 | Clean structured front page with item URLs | High for discovery | Crawl `/item*`; store HN discussion context |
| KrebsOnSecurity | 100 | Article content available, with advertising noise, about 49 KB | Medium-high | Crawl dated article paths and exclude WordPress noise |
| TechCabal | 100 | Current article listing and dates, about 33 KB | High | Crawl dated article paths |
| Techweez | 99 | Clean current article listing and dates, about 27 KB | High | Crawl dated article paths |
| TLDR tech | 69 | Strong dated archive coverage from mapping | High | Crawl tech/AI/dev/infosec archive paths |
| The Batch | 99 | Clean issue archive with dates and article links, about 14 KB | High | Crawl `/the-batch/*`, excluding tags/search |

The enabled scopes and limits are encoded in [`config/seeds.json`](../config/seeds.json). The initial configured run is intentionally bounded: most sources are capped at 15 pages, The Batch at 10, and Techmeme at one current-page scrape.

## Sources that should not be deep-crawled

- **X accounts:** use the configured X search terms (`from:... since:{start_date}`) or an X API. Public profile pages are dynamic and are better treated as discovery inputs.
- **YouTube channels:** use YouTube RSS or the YouTube Data API for upload freshness, then scrape selected video pages only for context/transcripts.
- **Newsletters:** prefer RSS/archive pages. TLDR and The Batch have good archive structures; individual newsletter providers should be added after their archive/RSS behavior is verified.
- **TechCrunch:** direct scraping was blocked by a Cloudflare verification page during this audit. Keep it in search/RSS mode until a stable permitted route is available.

## Run order

1. Review the enabled source scopes.
2. Run one small pass: `uv run techtember crawl-sites --limit 3`.
3. Inspect `data/runs/` and query results with `uv run techtember search ...`.
4. Raise per-site limits only for sources producing useful article records.
5. Add RSS/API adapters for X, YouTube, newsletters, and TechCrunch where direct crawling is weak.
