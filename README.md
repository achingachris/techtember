# Techtember

Techtember is a focused, searchable web corpus for technology-related content. It uses the official Firecrawl Python SDK for discovery and collection, then normalizes pages into a local SQLite database with full-text search.

## Quick start

Requirements: Python 3.9+ and `uv`.

```bash
cp .env.example .env
# Add your FIRECRAWL_API_KEY to .env
uv sync
uv run python -m unittest discover -s tests -v
uv run techtember smoke-test
```

The smoke test makes one real scrape request. It is intentionally separate from the test suite so unit tests never spend API credits.

## Commands

```bash
# Run the complete configured collection: all searches, then all enabled sites.
uv run techtember run-all

# Run a smaller complete collection while checking the setup.
uv run techtember run-all --limit 3

# Run the configured Google and open-web searches.
uv run techtember discover --platform google --limit 10
uv run techtember discover --platform web --limit 10

# Run the configured X searches. X terms are automatically restricted to x.com/twitter.com.
uv run techtember discover --platform x --limit 10

# Print the exact configured terms before running them.
uv run techtember queries --platform x
uv run techtember queries --platform google
uv run techtember queries --platform web

# Run one additional search query.
uv run techtember discover "AI developer tools" --limit 5

# Scrape the configured Techmeme front page.
uv run techtember scrape https://techmeme.com

# Crawl the configured Verge technology section with its source filters.
uv run techtember crawl https://www.theverge.com/tech --limit 3 \
  --include-path '/tech/*' --exclude-path '/video/*' --max-depth 1

# Crawl every enabled source listed in config/seeds.json.
uv run techtember crawl-sites --limit 3

# Inspect the Techmeme site map without storing pages.
uv run techtember map https://techmeme.com

# Search and export the local corpus.
uv run techtember search "artificial intelligence"
uv run techtember export --query "artificial intelligence" --format csv \
  --output data/artificial-intelligence.csv
uv run techtember stats
```

Global options must appear before the command:

```bash
uv run techtember --config config/seeds.json --db data/custom.db discover
```

## Configuration

Edit [`config/seeds.json`](config/seeds.json) to change:

- legacy `queries` or named `search_terms` for `x`, `google`, and `web`;
- named `crawl_sites` entries;
- per-site mode (`scrape` or `crawl`), include/exclude path patterns, limits, and depth;
- terms used for deterministic topic extraction and relevance scoring;
- included and excluded domains;
- result and crawl limits;
- retry, backoff, and request-spacing controls;
- the local database path.

The API key is read from `FIRECRAWL_API_KEY` in the environment or `.env`. It is never written to the database or logs.

Search terms containing `{start_date}`, `{today}`, or `{year}` are expanded at runtime. Set `TECHTEMBER_START_DATE=2026-09-01` when you want a fixed crawl window.

### Adding search terms

Use named entries so the same query can be reviewed or run by platform:

```json
{
  "name": "Cloud launches on X",
  "platform": "x",
  "query": "(cloud OR Kubernetes) (launch OR release)",
  "include_domains": ["x.com", "twitter.com"]
}
```

For `x`, the crawler adds `site:x.com OR site:twitter.com` filters automatically. Custom `include_domains` entries are converted to the same portable `site:` query operators, which works with the installed Firecrawl SDK. `google` and `web` use Firecrawl's general web search; Google operators such as `site:example.com` can be included directly in the query.

### Adding sites to crawl

Add public URLs to `crawl_sites`; the `crawl-sites` and `run-all` commands only run entries with `enabled: true`:

```json
{
  "name": "Example technology blog",
  "url": "https://example.com/blog",
  "enabled": true,
  "limit": 25,
  "min_relevance_score": 0.15
}
```

The starter list is bounded and includes the audited sources; TechCrunch remains disabled until its Cloudflare challenge is resolved. Remove or disable entries you do not want to crawl.

The provided source audit and crawl recommendations are in [`docs/SOURCE_AUDIT.md`](docs/SOURCE_AUDIT.md). Start with a small run before increasing limits:

```bash
uv run techtember crawl-sites --limit 3
```

`run-all` uses all configured `search_terms` first and then crawls all enabled `crawl_sites`. Its `--limit` overrides both the number of results per search and the maximum pages per site. Disable a source or remove a search term in `config/seeds.json` when it should not run.

Collection commands also write a small audit manifest under `data/runs/` containing the command arguments and counts. Raw page responses are retained in the database's `raw_json` column; the database itself is ignored by Git.

## Architecture

```text
Firecrawl search/map/crawl/scrape
                |
                v
      URL canonicalization + scoring
                |
                v
       SQLite records + FTS5 index
                |
                v
       CLI search / JSON / CSV export
```

The first release intentionally keeps enrichment deterministic and inexpensive. A future enrichment stage can use Firecrawl's agent endpoint for pages that need structured extraction, while recurring change detection can be added with Firecrawl monitoring.

## Scope and operating rules

- Configure a finite set of queries and domains; do not attempt an unrestricted whole-web crawl.
- Crawl only public pages that you are allowed to access.
- Review each source's robots.txt and terms of service.
- Keep API keys in environment variables and avoid committing raw crawl data.
- Use `--limit` and the config limits to control cost and volume.
