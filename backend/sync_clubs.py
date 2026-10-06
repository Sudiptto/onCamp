import argparse
import json
from pathlib import Path

from app import create_app
from app.college_config import get_college_config
from app.extensions import db
from app.models import Club

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "data" / "clubs.json"


def load_clubs_file(input_path: Path) -> list[dict]:
    if not input_path.exists():
        raise FileNotFoundError(
            f"No clubs file at {input_path}. Run run_full_pipeline.py first."
        )
    with open(input_path, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def sync_clubs(records: list[dict], seed_account: str) -> dict:
    created, updated, skipped = 0, 0, 0             # three counters start at zero

    for record in records:                          # loop over every club dict in the JSON
        handle = (record.get("username") or "").strip()
        if not handle:                              # THIS is the check
            skipped += 1                            
            continue                             
            # if this record doesn't have the one piece of data we absolutely need, don't crash, just count it and move on.

        display_name = (record.get("full_name") or handle).strip()

        club = Club.query.filter_by(instagram_handle=handle).first()
        if club is None:
            club = Club(
                name=display_name,
                instagram_handle=handle,
                seed_account=seed_account,
                is_active=True,
            )
            db.session.add(club)
            created += 1
        else:
            club.name = display_name
            club.seed_account = seed_account
            club.is_active = True
            updated += 1

    db.session.commit()
    return {"created": created, "updated": updated, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync AI-approved clubs.json into the Club table."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--college",
        default="hunter",
        help="College key used to resolve the seed_account stored on each Club row.",
    )
    parser.add_argument("--seed-account", default=None)
    args = parser.parse_args()

    # figure out which seed_account value to store on each club:
    # use --seed-account if given, otherwise the college's default
    config = get_college_config(args.college)
    seed_account = args.seed_account or config["seed_account"]
    config = get_college_config(args.college)
    seed_account = args.seed_account or config["seed_account"]

    records = load_clubs_file(args.input)

    app = create_app()
    with app.app_context():
        summary = sync_clubs(records, seed_account=seed_account)

    print(json.dumps({"input": str(args.input), **summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())