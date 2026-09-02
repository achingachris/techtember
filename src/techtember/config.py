"""Configuration loading without requiring a dotenv dependency."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_TERMS = [
    "technology",
    "software",
    "engineering",
    "developer",
    "programming",
    "artificial intelligence",
    "machine learning",
    "cloud",
    "cybersecurity",
    "data",
    "startup",
    "open source",
]


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries, without overriding real environment values."""

    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def load_json_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("Config file must contain a JSON object")
    return value


@dataclass
class Settings:
    """Runtime settings resolved from environment and the seed config."""

    api_key: Optional[str]
    database_path: Path
    data_dir: Path
    queries: List[str] = field(default_factory=list)
    terms: List[str] = field(default_factory=lambda: list(DEFAULT_TERMS))
    include_domains: List[str] = field(default_factory=list)
    exclude_domains: List[str] = field(default_factory=list)
    max_search_results: int = 10
    max_crawl_pages: int = 25
    min_relevance_score: float = 0.0
    max_retries: int = 2
    backoff_seconds: float = 1.0
    request_interval_seconds: float = 0.25


def load_settings(config_path: Path, db_override: Optional[Path] = None) -> Settings:
    """Resolve settings and create no files until a command actually needs them."""

    load_dotenv(Path(".env"))
    config = load_json_config(config_path)
    configured_db = Path(
        str(config.get("database_path", os.getenv("TECHTEMBER_DB", "data/techtember.db")))
    )
    database_path = db_override or configured_db
    data_dir = Path(str(config.get("data_dir", "data")))

    def list_value(key: str, default: List[str]) -> List[str]:
        value = config.get(key, default)
        if not isinstance(value, list):
            raise ValueError("Config value '%s' must be a list" % key)
        return [str(item).strip() for item in value if str(item).strip()]

    return Settings(
        api_key=os.getenv("FIRECRAWL_API_KEY") or None,
        database_path=database_path,
        data_dir=data_dir,
        queries=list_value("queries", []),
        terms=list_value("terms", DEFAULT_TERMS),
        include_domains=list_value("include_domains", []),
        exclude_domains=list_value("exclude_domains", []),
        max_search_results=int(config.get("max_search_results", 10)),
        max_crawl_pages=int(config.get("max_crawl_pages", 25)),
        min_relevance_score=float(config.get("min_relevance_score", 0.0)),
        max_retries=int(config.get("max_retries", 2)),
        backoff_seconds=float(config.get("backoff_seconds", 1.0)),
        request_interval_seconds=float(config.get("request_interval_seconds", 0.25)),
    )
