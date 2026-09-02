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
# Search configured seed queries, scrape results, and index them.
uv run techtember discover

# Use a one-off query.
uv run techtember discover "AI developer tools" --limit 5

# Scrape or crawl a known public URL.
uv run techtember scrape https://example.com/article
uv run techtember crawl https://example.com --limit 10

# Inspect a site map without storing pages.
uv run techtember map https://example.com

# Search and export the local corpus.
uv run techtember search python cloud
uv run techtember export --query "python" --format csv --output data/python.csv
uv run techtember stats
```

Global options must appear before the command:

```bash
uv run techtember --config config/seeds.json --db data/custom.db discover
```

## Configuration

Edit [`config/seeds.json`](config/seeds.json) to change:

- discovery queries;
- terms used for deterministic topic extraction and relevance scoring;
- included and excluded domains;
- result and crawl limits;
- retry, backoff, and request-spacing controls;
- the local database path.

The API key is read from `FIRECRAWL_API_KEY` in the environment or `.env`. It is never written to the database or logs.

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
