import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

from app import create_app
from app.models import Club, College
from app.services.hiker_client import HikerClient
from jobs.post_extraction.club_posts import process_club_posts
from jobs.post_extraction.pipeline import DEFAULT_OUTPUT_DIR

ROOT = Path(__file__).resolve().parents[2]
MAX_POSTS = 12  # one HikerAPI page


def _ask(prompt: str, default: str) -> str:
    answer = input(f"{prompt} [{default}]: ").strip()
    return answer or default


def _show(row) -> None:
    print(f"\n  post_id:      {row.post_id}")
    print(f"  link:         {row.post_url}")
    print(f"  posted_at:    {row.posted_at} UTC")
    print(f"  is_event:     {row.is_event}")
    print(f"  title:        {row.title}")
    print(f"  start / end:  {row.start_time} / {row.end_time} (campus time)")
    print(f"  location:     {row.location}")
    print(f"  free food:    {row.has_free_food}")
    print(f"  google form:  {row.google_form_url}")
    print(f"  caption:      {(row.caption or '')[:160]!r}")


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT.parent / ".env")
    parser = argparse.ArgumentParser(description="Extract event details from one club's recent posts.")
    parser.add_argument("--username", help="Club Instagram handle (prompted if omitted)")
    parser.add_argument("--count", type=int, help="How many recent posts to check (prompted if omitted)")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt")
    args = parser.parse_args(argv)

    username = args.username or _ask("Club Instagram handle", "hunter_bsa")
    count = args.count or int(_ask(f"How many recent posts to check (1-{MAX_POSTS})", "3"))
    count = max(1, min(count, MAX_POSTS))

    app = create_app()
    with app.app_context():
        club = Club.query.filter(Club.instagram_handle.ilike(username)).first()
        if club is None:
            print(f"No club with handle '{username}' in the database.", file=sys.stderr)
            return 1
        if club.instagram_user_id is None:
            print(f"{club.instagram_handle} has no Instagram user id, cannot fetch posts.", file=sys.stderr)
            return 1
        college = College.query.get(club.college_id)
        print(f"Club: {club.name} (@{club.instagram_handle}) | College: {college.name}")

        if not args.yes and _ask(f"Fetch and check the latest {count} posts?", "y").lower() not in {"y", "yes"}:
            print("Cancelled.")
            return 0

        raw = HikerClient().get_user_medias(club.instagram_user_id)
        # Keep the raw response for inspection (data/ is gitignored).
        DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (DEFAULT_OUTPUT_DIR / f"{club.instagram_handle}.json").write_text(
            json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        result = process_club_posts(club, raw, count)
        print(
            f"\nFetched {result['fetched']} | already checked (skipped) {result['already_checked']} "
            f"| newly processed {result['processed']}"
        )
        for row in result["posts"]:
            _show(row)
        if result["error"]:
            print(f"\nStopped early, will retry from here next run: {result['error']}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
