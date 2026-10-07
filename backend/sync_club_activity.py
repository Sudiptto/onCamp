"""
Active clubs are re-checked roughly daily, inactive ones roughly monthly -- that interval is just logic here, not a stored column, 
since it's fully determined by status. next_check_at is what a future scheduler would query ("WHERE next_check_at <= now()") instead 
of re-checking every club every run.
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


def _parse_dt(value: str | None):
    return datetime.fromisoformat(value) if value else None


def sync_club_activity(records: list[dict], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    matched, unmatched = 0, 0

    for record in records:
        club = Club.query.filter_by(instagram_handle=record["username"]).first()
        if club is None:
            unmatched += 1
            continue

        activity = ClubActivity.query.filter_by(club_id=club.id).first()
        if activity is None:
            activity = ClubActivity(club_id=club.id, college_id=club.college_id)
            db.session.add(activity)

        status = record["status"]
        interval = (
            ACTIVE_CHECK_INTERVAL_DAYS if status == "active" else INACTIVE_CHECK_INTERVAL_DAYS
        )

        activity.college_id = club.college_id
        activity.status = status
        activity.last_post_id = record.get("last_post_id")
        activity.last_post_at = _parse_dt(record.get("last_post_at"))
        activity.next_check_at = now + timedelta(days=interval)
        activity.checked_at = now

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
        summary = sync_club_activity(records)

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