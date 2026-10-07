"""

Checks only the clubs that actually need to be checked.

The other scripts (sync_club_activity.py, run_activity_check.py) check every club in clubs.json every time, which is 
fine for testing but not great for a real schedule. This script asks the database which clubs are due for a check (new ones, 
or ones past their next_check_at), only runs those through the pipeline, and saves the results.

This is the one that would actually get run on a timer/cron job.

"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from app import create_app
from app.models import Club, ClubActivity, College
from jobs.activity_check import run as run_activity_check
from sync_club_activity import sync_club_activity

ROOT = Path(__file__).resolve().parent
DEFAULT_TMP_CLUBS = ROOT / "data" / "_due_clubs.json"
DEFAULT_OUTPUT = ROOT / "data" / "_due_activity_result.json"
DEFAULT_TEST_LIMIT = 5


def find_due_clubs(college_key: str, now: datetime | None = None) -> list[dict]:
    """Clubs for this college that are either never checked or past due."""
    now = now or datetime.now(timezone.utc)

    college = College.query.filter_by(key=college_key).first()
    if college is None:
        raise ValueError(f"No College row for key={college_key!r}.")

    due = (
        Club.query
        .outerjoin(ClubActivity, ClubActivity.club_id == Club.id)
        .filter(Club.college_id == college.id)
        .filter(
            (ClubActivity.id.is_(None))
            | (ClubActivity.next_check_at <= now)
        )
        .all()
    )
    return [{"user_id": club.instagram_handle, "username": club.instagram_handle} for club in due]


def main() -> int:
    load_dotenv(ROOT.parent / ".env")
    parser = argparse.ArgumentParser(
        description="Run activity_check only on clubs that are actually due."
    )
    parser.add_argument("--college", default="hunter")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_TEST_LIMIT,
        help=f"Only check the first N due clubs (default {DEFAULT_TEST_LIMIT}) to keep HikerAPI cost low.",
    )
    parser.add_argument("--all", action="store_true", help="Check every due club, no cap.")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
       # if the college name is wrong, print an error instead of crashing
        now = datetime.now(timezone.utc)
        try:
            due_clubs = find_due_clubs(args.college, now=now)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, indent=2))
            return 1

        if not due_clubs:
            print(json.dumps({"due_count": 0, "message": "Nothing due right now."}, indent=2))
            return 0

        DEFAULT_TMP_CLUBS.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_TMP_CLUBS.write_text(json.dumps(due_clubs, indent=2), encoding="utf-8")

        pipeline_result = run_activity_check(
            DEFAULT_TMP_CLUBS,
            DEFAULT_OUTPUT,
            limit=None if args.all else args.limit,
            now=now,
        )
        records = pipeline_result["active"] + pipeline_result["inactive"]
        sync_summary = sync_club_activity(
            records, now=now, errors=pipeline_result.get("errors")
        )

        print(json.dumps({
            "due_count": len(due_clubs),
            "checked_count": pipeline_result["checked_count"],
            "active_count": pipeline_result["active_count"],
            "inactive_count": pipeline_result["inactive_count"],
            "error_count": pipeline_result["error_count"],
            **sync_summary,
        }, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())