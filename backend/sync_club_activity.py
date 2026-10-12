"""Takes the results from activity_check and saves them into the database.

Clubs are matched by Instagram user id, or by handle if there's no id. The
pipeline already works out status and next_check_at, so this just stores them.

If a club couldn't be checked, a deleted or private account gets pushed out 30
days. A rate limit or server error is temporary, so nothing is saved and the
club is tried again next run.

Usage:
    cd backend
    python sync_club_activity.py --clubs data/clubs.json --limit 5
    python sync_club_activity.py --clubs data/clubs.json --all
"""

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from app import create_app
from app.extensions import db
from app.models import Club, ClubActivity
from jobs.activity_check import run as run_activity_check
from jobs.activity_check.buckets import INACTIVE_CHECK_INTERVAL_DAYS

ROOT = Path(__file__).resolve().parent
DEFAULT_CLUBS = ROOT / "data" / "clubs.json"
DEFAULT_OUTPUT = ROOT / "data" / "club_activity.json"
DEFAULT_TEST_LIMIT = 5

# The account is gone or off limits, so trying again soon won't help.
PERMANENT_ERROR_STATUS_CODES = {403, 404, 410}


def to_db_time(value: datetime | str | None) -> datetime | None:
    """Store every time as naive UTC so SQLite and Postgres compare them the same way."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _find_club(record: dict) -> Club | None:
    user_id = str(record.get("user_id") or "")
    if user_id:
        club = Club.query.filter_by(instagram_user_id=user_id).first()
        if club is not None:
            return club
    return Club.query.filter_by(instagram_handle=record.get("username", "")).first()


def _get_activity(club: Club) -> ClubActivity:
    activity = ClubActivity.query.filter_by(club_id=club.id).first()
    if activity is None:
        activity = ClubActivity(club_id=club.id, college_id=club.college_id)
        db.session.add(activity)
    activity.college_id = club.college_id
    return activity


def sync_club_activity(
    records: list[dict],
    now: datetime | None = None,
    errors: list[dict] | None = None,
) -> dict:
    checked_at = to_db_time(now or datetime.now(timezone.utc))
    matched, unmatched, backed_off, will_retry = 0, 0, 0, 0

    for record in records:
        club = _find_club(record)
        if club is None:
            unmatched += 1
            continue

        activity = _get_activity(club)
        activity.status = record["status"]
        activity.last_post_id = record.get("last_post_id")
        activity.last_post_at = to_db_time(record.get("last_post_at"))
        activity.next_check_at = to_db_time(record["next_check_at"])
        activity.checked_at = checked_at
        club.is_active = record["status"] == "active"
        matched += 1

    for error in errors or []:
        if error.get("status_code") not in PERMANENT_ERROR_STATUS_CODES:
            will_retry += 1
            continue

        club = _find_club(error)
        if club is None:
            unmatched += 1
            continue

        # We could not read this account, which says nothing about whether
        # the club is active, so is_active and the last post stay as they were.
        activity = _get_activity(club)
        activity.status = "error"
        activity.next_check_at = checked_at + timedelta(days=INACTIVE_CHECK_INTERVAL_DAYS)
        activity.checked_at = checked_at
        backed_off += 1

    db.session.commit()
    return {
        "matched": matched,
        "unmatched": unmatched,
        "backed_off": backed_off,
        "will_retry": will_retry,
    }


def main() -> int:
    load_dotenv(ROOT.parent / ".env")
    parser = argparse.ArgumentParser(
        description="Run activity_check and sync results into the club_activity table."
    )
    parser.add_argument("--clubs", type=Path, default=DEFAULT_CLUBS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_TEST_LIMIT,
        help=f"Only check the first N clubs (default {DEFAULT_TEST_LIMIT}) to keep HikerAPI cost low.",
    )
    parser.add_argument("--all", action="store_true", help="Check every club (one API call each).")
    args = parser.parse_args()

    pipeline_result = run_activity_check(
        args.clubs, args.output, limit=None if args.all else args.limit
    )
    records = pipeline_result["active"] + pipeline_result["inactive"]

    app = create_app()
    with app.app_context():
        summary = sync_club_activity(records, errors=pipeline_result["errors"])

    print(json.dumps({
        "checked_count": pipeline_result["checked_count"],
        "active_count": pipeline_result["active_count"],
        "inactive_count": pipeline_result["inactive_count"],
        "error_count": pipeline_result["error_count"],
        **summary,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
