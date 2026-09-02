"""Generate blog articles from the Techtember corpus using the article-writer skill.

Follows Chris Achinga's article-writer skill
(github.com/achingachris/my-skills, plugins/my-skills/skills/article-writer):
technical-tutorial voice, page bundles (index.md), no YAML front matter, no H1,
no em/en dashes, attribution footer, and a mechanical QA pass via qa_check.py.

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
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODELS_URL = "https://models.github.ai/inference/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o"
MAX_PAGES = 25
EXCERPT_CHARS = 1200
QA_SCRIPT = Path(__file__).parent / "article_writer" / "qa_check.py"
FOOTER = "*Written and Authored by Chris, Edited and assisted by Claude*"

SYSTEM_PROMPT = """You write blog articles in Chris Achinga's voice for me.chrisdevcode.com.
Chris is a Lead Software Engineer in Kenya (Mombasa/Nairobi), works with Python/Django,
React/Next.js, and React Native, and is active in African tech communities.

Article type: technical tutorial / tech roundup. Voice rules:
- lowercase throughout, except proper nouns (Python, Django, Kenya) and acronyms (API, CSS, AI).
- correct American English grammar, spelling, and punctuation. lowercase is a style choice,
  not an excuse for bad grammar.
- confident, direct, second person ("you should know"). short sentences. no filler.
- occasional self-deprecating humor and grounding analogies are welcome.
- ground every claim ONLY in the provided source material and cite sources as inline
  markdown links. never invent facts, quotes, or URLs.

Hard rules (non-negotiable):
1. NEVER use em dash (U+2014) or en dash (U+2013). Use commas, parentheses, colons, or semicolons.
2. NEVER use forced contrast framing ("it's not X, it's Y", "not just X, but Y").
3. Define acronyms at first use unless universally obvious (HTML, API, URL, CSS, JS).
4. No YAML front matter and no H1 heading in the body. Use H2 for sections, H3 for sub-topics.
5. Code blocks always have language tags.
6. The title is lowercase except proper nouns and acronyms.
7. Don't pad. Length matches depth.

Respond with ONLY a JSON object (no markdown fence around it) with these keys:
  "title": lowercase article title,
  "description": a short teaser (one sentence, playful is fine),
  "tags": array of 3-6 lowercase hyphen-separated tags,
  "body": the full article body in plain markdown (no front matter, no H1),
          ending with a 'sources' or 'today's runs' H2 section as instructed."""


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


def _call_model(token: str, model: str, messages) -> str:
    payload = json.dumps(
        {"model": model, "messages": messages, "temperature": 0.4, "max_tokens": 4000}
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
        raise SystemExit("Model returned an empty response")
    return content.strip()


def _parse_article_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise SystemExit("Model response was not valid JSON")
        data = json.loads(match.group(0))
    for key in ("title", "body"):
        if not str(data.get(key, "")).strip():
            raise SystemExit("Model response is missing '%s'" % key)
    data.setdefault("description", "")
    data.setdefault("tags", [])
    return data


def sanitize_body(body: str) -> str:
    """Mechanical safety net for the skill's hard rules."""

    body = body.strip()
    # Strip any YAML front matter the model emitted anyway.
    if body.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) == 3:
            body = parts[2].strip()
    lines = []
    in_code = False
    for line in body.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            lines.append(line)
            continue
        if not in_code:
            # Demote stray H1s; the title lives in Strapi's field, not the body.
            if re.match(r"^# \S", line):
                line = "#" + line
            line = line.replace(" — ", ", ").replace("—", ", ")
            line = line.replace(" – ", ", ").replace("–", "-")
        lines.append(line)
    body = "\n".join(lines).strip()
    if FOOTER not in body:
        body += "\n\n---\n\n%s" % FOOTER
    return body + "\n"


def _qa_check(index_path: Path, title: str) -> "tuple[int, str]":
    result = subprocess.run(
        [sys.executable, str(QA_SCRIPT), str(index_path), "--title", title],
        capture_output=True,
        text=True,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def _write_bundle(bundle_dir: Path, data: dict, extra_meta: dict) -> Path:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    index_path = bundle_dir / "index.md"
    index_path.write_text(sanitize_body(str(data["body"])), encoding="utf-8")
    meta = {
        "title": str(data["title"]).strip(),
        "description": str(data.get("description", "")).strip(),
        "tags": [str(tag).strip() for tag in data.get("tags", []) if str(tag).strip()],
        "author": "Chris Achinga",
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    meta.update(extra_meta)
    (bundle_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return index_path


def _generate(token: str, model: str, user_prompt: str, bundle_dir: Path, extra_meta: dict) -> Path:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    raw = _call_model(token, model, messages)
    data = _parse_article_json(raw)
    index_path = _write_bundle(bundle_dir, data, extra_meta)

    code, report = _qa_check(index_path, str(data["title"]))
    if code != 0:
        # One repair round: hand the QA failures back to the model.
        print("QA failures, requesting a fix:\n%s" % report)
        messages.append({"role": "assistant", "content": raw})
        messages.append(
            {
                "role": "user",
                "content": (
                    "The QA checker found these problems:\n%s\n\nFix every FAIL and return "
                    "the corrected article as the same JSON object, nothing else." % report
                ),
            }
        )
        data = _parse_article_json(_call_model(token, model, messages))
        index_path = _write_bundle(bundle_dir, data, extra_meta)
        code, report = _qa_check(index_path, str(data["title"]))
    print("QA report for %s:\n%s" % (index_path, report))
    if code != 0:
        # sanitize_body already fixed what can be fixed mechanically; don't fail the
        # unattended run over residual style findings, just surface them in the log.
        print("Warning: QA failures remain after repair; review this article.")
    return index_path


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
        "Today is %s (crawl run %s of the day). Below are %d web pages collected by "
        "Chris's automated technology crawler during this run window. Write ONE cohesive "
        "technical article (600-1000 words) that synthesizes the most interesting and "
        "technically substantive themes for developers. Group related items, explain why "
        "they matter to engineers, and link every claim to its source URL inline. End the "
        "body with an H2 'sources' section listing all URLs used.\n\n%s"
        % (day, args.run_label, len(pages), "\n\n".join(sources))
    )
    bundle_dir = Path(args.articles_dir) / day / ("run-%s" % args.run_label)
    return _generate(
        token,
        args.model,
        user_prompt,
        bundle_dir,
        {"date": day, "run": args.run_label, "pages": len(pages)},
    )


def _digest_article(args, token: str) -> Path:
    day = args.date or _today()
    day_dir = Path(args.articles_dir) / day
    run_files = sorted(day_dir.glob("run-*/index.md")) if day_dir.exists() else []
    if not run_files:
        print("No run articles found for %s; skipping digest." % day)
        raise SystemExit(0)

    previous = []
    for path in run_files:
        previous.append(
            "## Article: %s\n\n%s" % (path.parent.name, path.read_text(encoding="utf-8"))
        )
    user_prompt = (
        "Today is %s. Below are the %d articles generated earlier today from Chris's "
        "scheduled crawl runs. Write the FINAL daily article (800-1200 words): a polished "
        "editorial that synthesizes the whole day, highlights the most important "
        "developments, notes how the story evolved across runs, and references the earlier "
        "articles by their run name (e.g. 'as covered in run-1') as well as the original "
        "source URLs they cite. End the body with an H2 \"today's runs\" section naming "
        "each run article.\n\n%s" % (day, len(run_files), "\n\n---\n\n".join(previous))
    )
    bundle_dir = day_dir / "daily-digest"
    extra_meta = {
        "date": day,
        "type": "daily-digest",
        "source_articles": [p.parent.name for p in run_files],
    }
    return _generate(token, args.model, user_prompt, bundle_dir, extra_meta)


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
