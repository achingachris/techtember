"""Command-line interface for the Techtember corpus."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from .config import Settings, load_settings
from .firecrawl_client import FirecrawlClient, FirecrawlConfigurationError
from .pipeline import TechtemberPipeline
from .storage import Storage


def _summary_dict(summary: Any) -> dict:
    return {
        "discovered": summary.discovered,
        "fetched": summary.fetched,
        "stored": summary.stored,
        "skipped": summary.skipped,
        "failed": summary.failed,
        "errors": summary.errors,
    }


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/seeds.json"),
        help="JSON seed/config file (default: config/seeds.json)",
    )
    parser.add_argument("--db", type=Path, default=None, help="SQLite path override")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and query the Techtember web corpus")
    _add_common_arguments(parser)
    commands = parser.add_subparsers(dest="command", required=True)

    discover = commands.add_parser("discover", help="Search, scrape, and store relevant pages")
    discover.add_argument("queries", nargs="*", help="Search queries; defaults to config queries")
    discover.add_argument("--limit", type=int, default=None, help="Results per query")
    discover.add_argument("--min-score", type=float, default=None, help="Minimum relevance score")

    scrape = commands.add_parser("scrape", help="Scrape and store one URL")
    scrape.add_argument("url")
    scrape.add_argument("--query", default="", help="Optional query associated with the page")
    scrape.add_argument("--min-score", type=float, default=None, help="Minimum relevance score")

    crawl = commands.add_parser("crawl", help="Crawl and store pages from one site")
    crawl.add_argument("url")
    crawl.add_argument("--limit", type=int, default=None, help="Maximum pages")
    crawl.add_argument("--min-score", type=float, default=None, help="Minimum relevance score")

    map_command = commands.add_parser("map", help="List URLs discovered on a site")
    map_command.add_argument("url")
    map_command.add_argument("--search", default=None, help="Optional site-map search term")

    search = commands.add_parser("search", help="Search the local SQLite FTS index")
    search.add_argument("query", nargs="*", help="Search terms")
    search.add_argument("--limit", type=int, default=20)

    export = commands.add_parser("export", help="Export indexed pages")
    export.add_argument("--query", default="", help="Optional FTS query")
    export.add_argument("--limit", type=int, default=1000)
    export.add_argument("--format", choices=("json", "csv"), default="json")
    export.add_argument("--output", type=Path, default=None, help="Output path; defaults to stdout")

    commands.add_parser("stats", help="Show local corpus statistics")

    smoke = commands.add_parser("smoke-test", help="Make one real Firecrawl scrape request")
    smoke.add_argument("--url", default="https://firecrawl.dev")

    return parser


def _settings(args: argparse.Namespace):
    return load_settings(args.config, db_override=args.db)


def _pipeline(args: argparse.Namespace):
    settings = _settings(args)
    client = FirecrawlClient(
        api_key=settings.api_key,
        max_retries=settings.max_retries,
        backoff_seconds=settings.backoff_seconds,
        request_interval_seconds=settings.request_interval_seconds,
    )
    storage = Storage(settings.database_path)
    pipeline = TechtemberPipeline(
        client=client,
        storage=storage,
        terms=settings.terms,
        exclude_domains=settings.exclude_domains,
        include_domains=settings.include_domains,
    )
    return settings, storage, pipeline


def _print_summary(summary: Any) -> None:
    print(json.dumps(_summary_dict(summary), indent=2))


def _write_run_manifest(
    settings: Settings, command: str, args: argparse.Namespace, summary: Any
) -> Path:
    """Persist an audit-friendly summary without including secrets."""

    runs_dir = settings.data_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    manifest_path = runs_dir / ("%s-%s.json" % (timestamp, command))
    safe_args = {
        key: str(value)
        for key, value in vars(args).items()
        if key not in {"api_key", "password", "token"}
    }
    payload = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "args": safe_args,
        "summary": _summary_dict(summary),
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return manifest_path


def _run(args: argparse.Namespace) -> int:
    if args.command == "search":
        settings = _settings(args)
        with Storage(settings.database_path) as storage:
            rows = storage.search(" ".join(args.query), limit=args.limit)
            storage.export_json(rows)
        return 0

    if args.command == "export":
        settings = _settings(args)
        with Storage(settings.database_path) as storage:
            rows = (
                storage.search(args.query, limit=args.limit)
                if args.query
                else storage.list_pages(args.limit)
            )
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open("w", encoding="utf-8", newline="") as handle:
                    if args.format == "json":
                        storage.export_json(rows, handle)
                    else:
                        storage.export_csv(rows, handle)
                print("Exported %d records to %s" % (len(rows), args.output))
            elif args.format == "json":
                storage.export_json(rows)
            else:
                storage.export_csv(rows)
        return 0

    if args.command == "stats":
        settings = _settings(args)
        with Storage(settings.database_path) as storage:
            print(
                json.dumps(
                    {"database": str(settings.database_path), "pages": storage.count()},
                    indent=2,
                )
            )
        return 0

    if args.command == "map":
        settings = _settings(args)
        client = FirecrawlClient(
            api_key=settings.api_key,
            max_retries=settings.max_retries,
            backoff_seconds=settings.backoff_seconds,
            request_interval_seconds=settings.request_interval_seconds,
        )
        print(json.dumps(client.map(args.url, search=args.search), indent=2))
        return 0

    if args.command == "smoke-test":
        settings = _settings(args)
        client = FirecrawlClient(
            api_key=settings.api_key,
            max_retries=settings.max_retries,
            backoff_seconds=settings.backoff_seconds,
            request_interval_seconds=settings.request_interval_seconds,
        )
        page = client.scrape(args.url)
        print(
            json.dumps(
                {
                    "url": page.url,
                    "title": page.metadata.get("title", ""),
                    "characters": len(page.markdown),
                }
            )
        )
        return 0

    settings, storage, pipeline = _pipeline(args)
    try:
        if args.command == "discover":
            queries = args.queries or settings.queries
            if not queries:
                raise ValueError("No queries supplied and config contains no queries")
            summary = pipeline.discover(
                queries,
                limit=args.limit or settings.max_search_results,
                min_score=(
                    settings.min_relevance_score
                    if args.min_score is None
                    else args.min_score
                ),
            )
        elif args.command == "scrape":
            summary = pipeline.scrape(
                args.url,
                query=args.query,
                min_score=(
                    settings.min_relevance_score
                    if args.min_score is None
                    else args.min_score
                ),
            )
        elif args.command == "crawl":
            summary = pipeline.crawl(
                args.url,
                limit=args.limit or settings.max_crawl_pages,
                min_score=(
                    settings.min_relevance_score
                    if args.min_score is None
                    else args.min_score
                ),
            )
        else:
            raise ValueError("Unsupported command: %s" % args.command)
        _print_summary(summary)
        _write_run_manifest(settings, args.command, args, summary)
        return 1 if summary.failed else 0
    finally:
        storage.close()


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return _run(args)
    except FirecrawlConfigurationError as exc:
        print("Configuration error: %s" % exc, file=sys.stderr)
        return 2
    except Exception as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return 1
