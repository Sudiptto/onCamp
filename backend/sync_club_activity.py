"""

Takes the results from activity_check and saves them into the database.

Matches each club by its Instagram handle. Active clubs get re-checked roughly daily. Inactive ones get re-checked roughly monthly. 
That's just decided here based on status, not stored anywhere. next_check_at is what a scheduler would use later to only check clubs 
that are actually due.

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

ROOT = Path(__file__).resolve().parent
DEFAULT_CLUBS = ROOT / "data" / "clubs.json"
DEFAULT_OUTPUT = ROOT / "data" / "club_activity.json"
DEFAULT_TEST_LIMIT = 5

ACTIVE_CHECK_INTERVAL_DAYS = 1
INACTIVE_CHECK_INTERVAL_DAYS = 30
ERROR_BACKOFF_DAYS = 30  # don't hammer a broken account every single run


def _parse_dt(value: str | None):
    return datetime.fromisoformat(value) if value else None


def _interval_for(status: str) -> int:
    if status == "active":
        return ACTIVE_CHECK_INTERVAL_DAYS
    if status == "error":
        return ERROR_BACKOFF_DAYS
    return INACTIVE_CHECK_INTERVAL_DAYS


def sync_club_activity(
    records: list[dict], now: datetime | None = None, errors: list[dict] | None = None
) -> dict:
    now = now or datetime.now(timezone.utc)
    matched, unmatched = 0, 0

    # Normalize errors into the same shape as a normal record, tagged
    # status="error", so they go through one shared code path below
    # instead of a separate near-duplicate loop.
    error_records = [
        {"username": error.get("username", ""), "status": "error",
         "last_post_id": None, "last_post_at": None}
        for error in (errors or [])
    ]

    for record in records + error_records:
        club = Club.query.filter_by(instagram_handle=record["username"]).first()
        if club is None:
            unmatched += 1
            continue

        activity = ClubActivity.query.filter_by(club_id=club.id).first()
        if activity is None:
            activity = ClubActivity(club_id=club.id, college_id=club.college_id)
            db.session.add(activity)

        status = record["status"]
        interval = _interval_for(status)

        activity.college_id = club.college_id
        activity.status = status
        activity.last_post_id = record.get("last_post_id")
        activity.last_post_at = _parse_dt(record.get("last_post_at"))
        activity.next_check_at = now + timedelta(days=interval)
        activity.checked_at = now

        # Errored clubs aren't necessarily inactive -- we just couldn't
        # check them -- so don't flip is_active off based on an error.
        if status != "error":
            club.is_active = status == "active"
        matched += 1

    db.session.commit()
    return {"matched": matched, "unmatched": unmatched}


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
        summary = sync_club_activity(records, errors=pipeline_result.get("errors"))

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