"""Generate technical articles from the Techtember corpus via the GitHub Models API.

Modes:
    run    - write one article covering pages fetched today (per crawl run)
    digest - write the end-of-day article referencing today's run articles

Uses only the standard library so it runs in CI without extra dependencies.
"""

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODELS_URL = "https://models.github.ai/inference/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o"
MAX_PAGES = 25
EXCERPT_CHARS = 1200

SYSTEM_PROMPT = (
    "You are a senior technical writer producing a well-structured markdown article "
    "for a developer audience. Write clear, factual prose grounded ONLY in the "
    "provided source material. Cite sources inline as markdown links. Do not invent "
    "facts, quotes, or URLs. Start with a single H1 title line."
)


def _today() -> str:
    return dt.datetime.now(dt.timezone.utc).date().isoformat()


def _pages_for_day(db_path: Path, day: str):
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            """
            SELECT url, title, description, markdown, relevance_score, source
            FROM pages
            WHERE substr(fetched_at, 1, 10) = ?
            ORDER BY relevance_score DESC, fetched_at DESC
            LIMIT ?
            """,
            (day, MAX_PAGES),
        ).fetchall()
    finally:
        connection.close()
    return rows


def _call_model(token: str, model: str, system: str, user: str) -> str:
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.4,
            "max_tokens": 4000,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        MODELS_URL,
        data=payload,
        headers={
            "Authorization": "Bearer %s" % token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:2000]
        raise SystemExit("Model API error %s: %s" % (exc.code, detail))
    content = body["choices"][0]["message"]["content"]
    if not content or not content.strip():
        raise SystemExit("Model returned an empty article")
    return content.strip()


def _run_article(args, token: str) -> Path:
    day = args.date or _today()
    pages = _pages_for_day(Path(args.db), day)
    if not pages:
        print("No pages fetched on %s; skipping article." % day)
        raise SystemExit(0)

    sources = []
    for row in pages:
        excerpt = re.sub(r"\s+", " ", row["markdown"] or "")[:EXCERPT_CHARS]
        sources.append(
            "### %s\nURL: %s\nDescription: %s\nExcerpt: %s"
            % (row["title"] or row["url"], row["url"], row["description"] or "-", excerpt)
        )
    user_prompt = (
        "Today is %s (run %s of the day). Below are %d web pages collected by an "
        "automated technology crawler during this run window. Write ONE cohesive "
        "technical article (600-1000 words) that synthesizes the most interesting "
        "and technically substantive themes. Group related items, explain why they "
        "matter to engineers, and link every claim to its source URL. End with a "
        "'Sources' section listing all URLs used.\n\n%s"
        % (day, args.run_label, len(pages), "\n\n".join(sources))
    )
    article = _call_model(token, args.model, SYSTEM_PROMPT, user_prompt)

    out_dir = Path(args.articles_dir) / day
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ("run-%s.md" % args.run_label)
    header = "---\ndate: %s\nrun: %s\npages: %d\ngenerated: %s\n---\n\n" % (
        day,
        args.run_label,
        len(pages),
        dt.datetime.now(dt.timezone.utc).isoformat(),
    )
    path.write_text(header + article + "\n", encoding="utf-8")
    return path


def _digest_article(args, token: str) -> Path:
    day = args.date or _today()
    day_dir = Path(args.articles_dir) / day
    run_files = sorted(day_dir.glob("run-*.md")) if day_dir.exists() else []
    if not run_files:
        print("No run articles found for %s; skipping digest." % day)
        raise SystemExit(0)

    previous = []
    for path in run_files:
        previous.append("## Article: %s\n\n%s" % (path.name, path.read_text(encoding="utf-8")))
    user_prompt = (
        "Today is %s. Below are the %d technical articles generated earlier today "
        "from scheduled crawl runs. Write the FINAL daily article (800-1200 words): "
        "a polished editorial that synthesizes the whole day, highlights the most "
        "important developments, notes how the story evolved across runs, and "
        "references the earlier articles by their run name (e.g. 'as covered in "
        "run-1') as well as the original source URLs they cite. End with a 'Today's "
        "runs' list naming each run article.\n\n%s"
        % (day, len(run_files), "\n\n---\n\n".join(previous))
    )
    article = _call_model(token, args.model, SYSTEM_PROMPT, user_prompt)

    path = day_dir / "daily-digest.md"
    header = "---\ndate: %s\ntype: daily-digest\nsource_articles: %s\ngenerated: %s\n---\n\n" % (
        day,
        json.dumps([p.name for p in run_files]),
        dt.datetime.now(dt.timezone.utc).isoformat(),
    )
    path.write_text(header + article + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "digest"))
    parser.add_argument("--db", default="data/techtember.db")
    parser.add_argument("--articles-dir", default="articles")
    parser.add_argument("--date", default=None, help="ISO date override (default: today UTC)")
    parser.add_argument("--run-label", default="1", help="Run number within the day")
    parser.add_argument("--model", default=os.getenv("ARTICLE_MODEL", DEFAULT_MODEL))
    args = parser.parse_args()

    token = os.getenv("GITHUB_TOKEN") or os.getenv("MODELS_TOKEN")
    if not token:
        print("GITHUB_TOKEN is required for the GitHub Models API", file=sys.stderr)
        return 2

    if args.mode == "run":
        path = _run_article(args, token)
    else:
        path = _digest_article(args, token)
    print("Wrote %s" % path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
