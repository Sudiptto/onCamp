"""Loads the clubs from clubs.json into the Club table.

clubs.json comes from run_full_pipeline.py. Run seed_colleges.py first, every
club needs a college. Safe to run again, clubs are matched by Instagram user id
(or handle if there's no id) so rows get updated, not duplicated.

Usage:
    cd backend
    python sync_clubs.py --input data/clubs.json --college hunter
"""

import argparse
import json
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models import ArchivedClub, Club, College

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "data" / "clubs.json"


def load_clubs_file(input_path: Path) -> list[dict]:
    if not input_path.exists():
        raise FileNotFoundError(
            f"No clubs file at {input_path}. Run run_full_pipeline.py first."
        )
    with open(input_path, encoding="utf-8") as file_handle:
        return json.load(file_handle)


def _find_club(user_id: str | None, handle: str) -> Club | None:
    # The user id is stable, a handle is not, so try the id first.
    if user_id:
        club = Club.query.filter_by(instagram_user_id=user_id).first()
        if club is not None:
            return club
    return Club.query.filter_by(instagram_handle=handle).first()


def sync_clubs(records: list[dict], college_key: str) -> dict:
    college = College.query.filter_by(key=college_key).first()
    if college is None:
        raise ValueError(
            f"No College row for key={college_key!r}. Run seed_colleges.py first."
        )

    created, updated, skipped = 0, 0, 0
    archived = ArchivedClub.query.all()
    archived_ids = {a.instagram_user_id for a in archived if a.instagram_user_id}
    archived_handles = {a.instagram_handle for a in archived}

    for record in records:
        handle = (record.get("username") or "").strip()
        if not handle:
            # Can't store a club without a handle, so count it and move on.
            skipped += 1
            continue

        user_id = str(record.get("user_id") or "").strip() or None
        display_name = (record.get("full_name") or handle).strip()
        profile_pic_url = (record.get("profile_pic_url") or "").strip() or None

        # Archived clubs (no post in 2+ years) stay out until restored manually.
        if user_id in archived_ids or handle in archived_handles:
            skipped += 1
            continue

        club = _find_club(user_id, handle)
        if club is None:
            club = Club(college_id=college.id, is_active=True)
            db.session.add(club)
            created += 1
        else:
            # is_active is left alone here, the activity check owns that field.
            updated += 1

        club.college_id = college.id
        club.name = display_name
        club.instagram_handle = handle
        club.instagram_user_id = user_id
        club.profile_pic_url = profile_pic_url

    db.session.commit()
    return {"created": created, "updated": updated, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync clubs.json into the Club table."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--college",
        default="hunter",
        help="College key, must already exist (see seed_colleges.py).",
    )
    args = parser.parse_args()

    records = load_clubs_file(args.input)

    app = create_app()
    with app.app_context():
        summary = sync_clubs(records, college_key=args.college)

    print(json.dumps({"input": str(args.input), **summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
