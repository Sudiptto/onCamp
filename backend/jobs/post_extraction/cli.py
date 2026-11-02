"""Scans club Instagram posts and saves the upcoming events found in them.

This is the cron entry point for the post step. Each run:
  1. moves events that already happened into archived_events,
  2. picks the clubs to scan (active clubs not scanned in the last 2 days, or the
     clubs named with --username),
  3. fetches each club's newest posts, skips ones already checkpointed, asks the AI
     about the rest and stores only upcoming events.

Usage:
    cd backend
    python run_post_extraction.py --due --college hunter --limit 5
    python run_post_extraction.py --username hunter_bsa another_club --count 3
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from app import create_app
from app.models import Club
from app.services.event_archive import archive_past_events
from app.services.hiker_client import HikerAPIError, HikerClient
from jobs.post_extraction.club_posts import find_clubs_due_for_post_scan, process_club_posts
from jobs.post_extraction.pipeline import DEFAULT_OUTPUT_DIR

ROOT = Path(__file__).resolve().parents[2]
MAX_POSTS = 12  # one HikerAPI page
DEFAULT_COUNT = 3


def _ask(prompt: str, default: str) -> str:
    answer = input(f"{prompt} [{default}]: ").strip()
    return answer or default


def _show(event) -> None:
    print(f"    EVENT {event.title!r} | {event.start_time} -> {event.end_time} | {event.location}")
    print(f"          free food: {event.is_free_food} | form: {event.google_form_url} | {event.source_url}")


def scan_club(club: Club, client: HikerClient, count: int, now: datetime) -> dict:
    print(f"\n{club.name} (@{club.instagram_handle})")
    raw = client.get_user_medias(club.instagram_user_id)
    # Keep the raw response for inspection (data/ is gitignored).
    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (DEFAULT_OUTPUT_DIR / f"{club.instagram_handle}.json").write_text(
        json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    result = process_club_posts(club, raw, count, now=now)
    print(
        f"  fetched {result['fetched']} | already checked {result['already_checked']} | "
        f"processed {result['processed']} | events added {len(result['events'])} | "
        f"not events {result['not_events']} | past (skipped) {result['past_events']} | "
        f"undated (skipped) {result['undated_events']} | "
        f"duplicates (skipped) {result['duplicate_events']}"
    )
    for event in result["events"]:
        _show(event)
    if result["error"]:
        print(f"  stopped early, will retry from here next run: {result['error']}", file=sys.stderr)
    return result


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT.parent / ".env")
    parser = argparse.ArgumentParser(description="Find upcoming events in club Instagram posts.")
    parser.add_argument("--due", action="store_true", help="Scan active clubs that are due (every 2 days)")
    parser.add_argument("--college", default="hunter", help="College key used with --due")
    parser.add_argument("--limit", type=int, help="Max clubs to scan with --due")
    parser.add_argument("--username", nargs="+", help="Scan these club handles regardless of schedule")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help=f"Recent posts per club (max {MAX_POSTS})")
    args = parser.parse_args(argv)
    count = max(1, min(args.count, MAX_POSTS))
    usernames = args.username
    if not args.due and not usernames:
        usernames = [_ask("Club Instagram handle", "hunter_bsa")]

    app = create_app()
    with app.app_context():
        now = datetime.now(timezone.utc)
        print(f"Archived {archive_past_events(now)} past event(s).")

        if args.due:
            try:
                clubs = find_clubs_due_for_post_scan(args.college, now=now, limit=args.limit)
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 1
        else:
            clubs = []
            for username in usernames:
                club = Club.query.filter(Club.instagram_handle.ilike(username)).first()
                if club is None or club.instagram_user_id is None:
                    print(f"Skipping '{username}': not in the database or has no Instagram user id.", file=sys.stderr)
                    continue
                clubs.append(club)

        print(f"{len(clubs)} club(s) to scan.")
        client = HikerClient()
        failed = False
        for club in clubs:
            try:
                failed |= scan_club(club, client, count, now)["error"] is not None
            except HikerAPIError as exc:
                print(f"  fetch failed for @{club.instagram_handle}: {exc}", file=sys.stderr)
                failed = True
                if exc.status_code == 429:
                    break  # rate limited, the rest would fail the same way
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
