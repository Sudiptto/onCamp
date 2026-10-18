"""Adds each college from college_config.py to the College table.

Run this once, and again whenever a college is added to COLLEGE_CONFIGS.
It has to run before sync_clubs.py, since every club points at a college.

Usage:
    cd backend
    python seed_colleges.py
"""

import json

from app import create_app
from app.college_config import COLLEGE_CONFIGS
from app.extensions import db
from app.models import College


def seed_colleges() -> dict:
    created, updated = 0, 0

    for key, config in COLLEGE_CONFIGS.items():
        college = College.query.filter_by(key=key).first()
        if college is None:
            college = College(key=key)
            db.session.add(college)
            created += 1
        else:
            updated += 1

        college.name = config["college_name"]
        college.seed_account = config["seed_account"]

    db.session.commit()
    return {"created": created, "updated": updated}


def main() -> int:
    app = create_app()
    with app.app_context():
        summary = seed_colleges()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
