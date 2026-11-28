"""Local LurkAPI post pilot. Fetches one page per club and optionally analyzes the newest post.

Does not write events. Raw responses stay under backend/data/lurk (gitignored).
Re-runs use that cache unless --refresh is set, because Lurk charges for its own cache too.
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.services.lurk_client import LurkAPIError, LurkClient
from jobs.lurk.posts import fetch_club_medias, newest_posts
from jobs.post_extraction.ai import ExtractionError, extract_with_deepseek_metered

ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "lurk"
TRACKER = ROOT / "docs" / "lurkapi-post-migration.md"
USAGE_MARKER = "<!-- usage-log -->"
DEFAULT_USERNAMES = ("hunter_bsa",)
DEFAULT_COLLEGE = "Hunter College"


def cache_path(output_dir: Path, username: str) -> Path:
    return output_dir / f"{username.lower()}.json"


def load_cache(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) and isinstance(data.get("raw"), dict) else None


def analyze_newest(post: dict[str, Any], club_name: str, college_name: str) -> dict[str, Any]:
    posted_at = datetime.fromisoformat(post["taken_at"])
    details, usage = extract_with_deepseek_metered(post["caption"], posted_at, club_name, college_name)
    return {"post_code": post["post_code"], "details": _jsonable(details), "usage": usage}


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def usage_row(record: dict[str, Any]) -> str:
    analysis = record.get("analysis") or {}
    usage = analysis.get("usage") or {}
    details = analysis.get("details") or {}
    note = record.get("error") or ("event" if details.get("is_event") else "not an event" if analysis else "fetch only")
    return (
        f"| {record.get('fetched_at', '')} | {record.get('username', '')} | "
        f"{record.get('credits_charged', 0)} | {record.get('credits_remaining', '')} | "
        f"{'yes' if record.get('from_cache') else 'no'} | "
        f"{usage.get('prompt_tokens', '')} | {usage.get('completion_tokens', '')} | "
        f"{usage.get('total_tokens', '')} | {record.get('newest_post_code') or ''} | {note} |"
    )


def append_usage(tracker: Path, rows: list[str]) -> None:
    if not rows or not tracker.exists():
        return
    text = tracker.read_text(encoding="utf-8")
    if USAGE_MARKER not in text:
        text += f"\n{USAGE_MARKER}\n"
    block = "\n".join(rows)
    tracker.write_text(text.replace(USAGE_MARKER, f"{USAGE_MARKER}\n{block}", 1), encoding="utf-8")


def run_username(
    username: str,
    client: LurkClient,
    output_dir: Path,
    analyze: bool,
    refresh: bool,
    college_name: str,
) -> dict[str, Any]:
    path = cache_path(output_dir, username)
    cached = None if refresh else load_cache(path)
    from_cache = cached is not None
    if cached is not None:
        raw = cached["raw"]
        medias = cached.get("medias")
        if not isinstance(medias, dict):
            from jobs.lurk.posts import lurk_posts_to_medias
            medias = lurk_posts_to_medias(raw)
        charged = 0
        remaining = client.credits_remaining
    else:
        before = len(client.calls)
        raw, medias = fetch_club_medias(client, username)
        call = client.calls[before] if len(client.calls) > before else {}
        charged = int(call.get("credits_charged") or 0)
        remaining = call.get("credits_remaining")

    posts = newest_posts(medias, count=12)
    newest = posts[0] if posts else None
    club_name = username
    if isinstance(raw, dict):
        for post in raw.get("posts") or []:
            user = post.get("user") if isinstance(post, dict) else None
            if isinstance(user, dict) and user.get("full_name"):
                club_name = user["full_name"]
                break

    analysis = None
    error = None
    if analyze and newest is not None:
        try:
            analysis = analyze_newest(newest, club_name, college_name)
        except ExtractionError as exc:
            error = str(exc)

    record = {
        "username": username,
        "club_name": club_name,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "from_cache": from_cache,
        "credits_charged": charged,
        "credits_remaining": remaining,
        "post_count": len(posts),
        "newest_post_code": newest["post_code"] if newest else None,
        "newest_taken_at": newest["taken_at"] if newest else None,
        "analysis": analysis,
        "error": error,
        "raw": raw,
        "medias": medias,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Local LurkAPI newest-post pilot. Does not write the database.")
    parser.add_argument("--username", nargs="+", default=list(DEFAULT_USERNAMES))
    parser.add_argument("--analyze", action="store_true", help="Run DeepSeek on the newest post only")
    parser.add_argument("--refresh", action="store_true", help="Ignore the local cache and spend a credit")
    parser.add_argument("--college", default=DEFAULT_COLLEGE)
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--tracker", type=Path, default=TRACKER)
    args = parser.parse_args(argv)

    client = LurkClient()
    failed = False
    rows = []
    for username in args.username:
        print(f"@{username}")
        try:
            record = run_username(
                username, client, args.output_dir, args.analyze, args.refresh, args.college
            )
        except LurkAPIError as exc:
            print(f"  fetch failed: {exc}", file=sys.stderr)
            failed = True
            rows.append(usage_row({
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "username": username,
                "credits_charged": client.credits_charged,
                "credits_remaining": client.credits_remaining,
                "error": exc.code or str(exc),
            }))
            if exc.status_code in {402, 429}:
                break
            continue
        source = "cache" if record["from_cache"] else f"{record['credits_charged']} credit"
        print(
            f"  {source} | posts {record['post_count']} | newest {record['newest_post_code']} "
            f"| remaining {record['credits_remaining']}"
        )
        if record["analysis"]:
            details = record["analysis"]["details"]
            usage = record["analysis"]["usage"]
            print(
                f"  analysis is_event={details.get('is_event')} title={details.get('title')!r} "
                f"| tokens {usage.get('total_tokens')}"
            )
        if record["error"]:
            print(f"  analysis failed: {record['error']}", file=sys.stderr)
            failed = True
        rows.append(usage_row(record))
    append_usage(args.tracker, rows)
    print(f"Lurk credits this process: {client.credits_charged}; remaining: {client.credits_remaining}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
