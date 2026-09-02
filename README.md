# Techtember

Techtember is a focused, searchable web corpus for technology-related content. It uses no-credit RSS/HTTP collection by default and reserves the official Firecrawl Python SDK for sources that need browser-grade crawling, then normalizes pages into a local SQLite database with full-text search.

## Quick start

Requirements: Python 3.9+ and `uv`. A Firecrawl API key is recommended, but collection commands can use the no-credit fallbacks when the key is missing or Firecrawl is unavailable.

```bash
cp .env.example .env
# Add your FIRECRAWL_API_KEY to .env
uv sync
uv run python -m unittest discover -s tests -v
uv run techtember smoke-test
```

The smoke test makes one real Firecrawl scrape request and therefore requires a Firecrawl API key. It is intentionally separate from the test suite so unit tests never spend API credits.

## Commands

```bash
# Run the complete configured collection: all searches, then all enabled sites.
uv run techtember run-all

# Run a smaller complete collection while checking the setup.
uv run techtember run-all --limit 3

# Run the configured Google and open-web searches with no-credit providers.
uv run techtember discover --platform google --limit 10
uv run techtember discover --platform web --limit 10

# Run the configured X searches with no-credit providers.
uv run techtember discover --platform x --limit 10

# Use Firecrawl for a search when a browser-grade result set is needed.
uv run techtember discover --platform google --provider firecrawl --limit 10

# Print the exact configured terms before running them.
uv run techtember queries --platform x
uv run techtember queries --platform google
uv run techtember queries --platform web

# Run one additional search query.
uv run techtember discover "AI developer tools" --limit 5

# Scrape the configured hard source with Firecrawl (the default for this explicit command).
uv run techtember scrape https://techmeme.com

# Scrape a source with no-credit providers.
uv run techtember scrape https://techmeme.com --provider fallback

# Crawl the configured Verge technology section with no-credit providers.
uv run techtember crawl https://www.theverge.com/tech --limit 3 \
  --provider fallback --include-path '/tech/*' --exclude-path '/video/*' --max-depth 1

# Crawl every enabled source using its configured provider.
uv run techtember crawl-sites --limit 3

# Inspect the Techmeme site map without storing pages.
uv run techtember map https://techmeme.com

# Search and export the local corpus.
uv run techtember search "artificial intelligence"
uv run techtember export --query "artificial intelligence" --format csv \
  --output data/artificial-intelligence.csv
uv run techtember stats

# Prepare a detailed evidence brief for GitHub Copilot or another writing agent.
uv run techtember prepare-article \
  --topic "Techtember technology trends" \
  --limit 60 \
  --output articles/techtember-technology-trends.md
```

Global options must appear before the command:

```bash
uv run techtember --config config/seeds.json --db data/custom.db discover
```

## Configuration

Edit [`config/seeds.json`](config/seeds.json) to change:

- legacy `queries` or named `search_terms` for `x`, `google`, and `web`;
- named `crawl_sites` entries;
- per-site mode (`scrape` or `crawl`), provider (`fallback` or `firecrawl`), RSS feeds, include/exclude path patterns, limits, and depth;
- terms used for deterministic topic extraction and relevance scoring;
- included and excluded domains;
- result and crawl limits;
- retry, backoff, and request-spacing controls;
- fallback enablement, timeout, forced-fallback mode, and optional SearXNG URL;
- the local database path.

The API key is read from `FIRECRAWL_API_KEY` in the environment or `.env`. It is never written to the database or logs. If Firecrawl is unavailable, `discover`, `scrape`, `crawl`, `crawl-sites`, `map`, and `run-all` continue through the fallback providers when `fallback_enabled` is true.

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
  "provider": "fallback",
  "rss_feeds": ["https://example.com/feed/"],
  "limit": 25,
  "min_relevance_score": 0.15
}
```

The starter list is bounded and includes the audited sources; TechCrunch remains disabled until its Cloudflare challenge is resolved. Remove or disable entries you do not want to crawl.

The provided source audit and crawl recommendations are in [`docs/SOURCE_AUDIT.md`](docs/SOURCE_AUDIT.md). Start with a small run before increasing limits:

```bash
uv run techtember crawl-sites --limit 3
```

`run-all` uses no-credit providers for all configured `search_terms`, then uses each site's configured `provider` for enabled `crawl_sites`. Its `--limit` overrides both the number of results per search and the maximum pages per site. Disable a source or remove a search term in `config/seeds.json` when it should not run.

### Provider policy

Configured sites default to `provider: "fallback"`. Set `provider: "firecrawl"` only for a source that needs JavaScript rendering, browser interaction, Cloudflare handling, or deeper link traversal. The starter configuration reserves Firecrawl for Techmeme's dynamic front page; TechCrunch is also marked as Firecrawl-only when it is re-enabled. All other enabled sources use RSS/Atom or direct HTTP first.

The explicit `discover` command also defaults to no-credit providers. Add `--provider firecrawl` when a particular search needs Firecrawl. Explicit `scrape` and `crawl` commands default to Firecrawl because they are manual requests for a URL; pass `--provider fallback` to keep them no-credit.

### No-credit fallbacks

Fallback collection is enabled in the starter config. The provider order is:

1. RSS or Atom feeds listed in a site's `rss_feeds` setting;
2. RSS or Atom feeds advertised by the site's HTML, plus common feed paths such as `/feed/` and `/rss.xml`;
3. a self-hosted SearXNG instance for search, when `TECHTEMBER_SEARXNG_URL` is set;
4. Google News RSS for search discovery;
5. bounded same-host HTML link crawling and standard-library text extraction.

The RSS and direct HTTP paths require no additional package or Firecrawl credit. RSS entries store the feed summary; direct HTML fallback stores the extracted page text. To use an open-source search engine, run SearXNG locally and set its URL in `.env`:

```bash
TECHTEMBER_SEARXNG_URL=http://localhost:8080 uv run techtember run-all --limit 3
```

To exercise the fallback path without making any Firecrawl requests:

```bash
TECHTEMBER_FORCE_FALLBACK=true uv run techtember run-all --limit 3
```

If Firecrawl returns a credit, quota, or rate-limit error, Techtember disables Firecrawl for the rest of that run and continues with the fallbacks. A `Fallback providers used` line is printed on stderr when this happens. `smoke-test` remains Firecrawl-only by design.

Collection commands also write a small audit manifest under `data/runs/` containing the command arguments and counts. `run-all` additionally writes a citation-ready article brief under `data/runs/`. Raw page responses are retained in the database's `raw_json` column; the database itself is ignored by Git.

## Article agent handoff

After collection, GitHub Copilot can read the latest `data/runs/*-article-brief.md` and write a detailed technical article with source links. Repository-specific instructions are in [`.github/copilot-instructions.md`](.github/copilot-instructions.md). To create a focused brief without running the crawler, use `prepare-article` with a local FTS query:

```bash
uv run techtember prepare-article \
  --topic "AI agents and the September technology launch season" \
  --query "artificial intelligence" \
  --limit 60 \
  --output articles/ai-agents-techtember.md
```

The generated brief contains an assignment, a diverse evidence index, original URLs, publication metadata, relevance scores, and bounded source extracts. The agent should treat it as evidence, verify important claims against the linked pages, and save the finished article under `articles/`.

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
