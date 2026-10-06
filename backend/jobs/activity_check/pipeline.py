import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.hiker_client import HikerAPIError, HikerClient
from jobs.activity_check.buckets import classify_activity
from jobs.activity_check.posts import parse_latest_post


def _record(club: dict[str, Any], client: Any, now: datetime) -> dict[str, Any]:
    latest = parse_latest_post(client.get_user_medias(club["user_id"]))
    last_post_at = latest["taken_at"] if latest else None
    return {
        "user_id": str(club["user_id"]),
        "username": club.get("username", ""),
        "last_post_at": last_post_at.isoformat() if last_post_at else None,
        "last_post_id": latest["post_id"] if latest else None,
        "last_post_code": latest["post_code"] if latest else None,
        "checked_at": now.isoformat(),
        **classify_activity(last_post_at, now),
    }


def run(
    clubs_path: Path,
    output_path: Path,
    limit: int | None = None,
    client: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Split clubs.json into active and inactive clubs by last post date (one HikerAPI call per club).

    Output goes to a JSON file for now; each record is shaped as one row of a future
    club_activity table (keyed by user_id, FK to clubs), so the DB write would replace
    the file write at the end of this function.
    """
    clubs = json.loads(Path(clubs_path).read_text(encoding="utf-8-sig"))
    if limit is not None:
        clubs = clubs[:limit]
    client = client or HikerClient()
    now = now or datetime.now(timezone.utc)

    active: list[dict[str, Any]] = []
    inactive: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for club in clubs:
        try:
            record = _record(club, client, now)
        except HikerAPIError as exc:
            # One failing account must not abort the run; it stays out of both lists.
            errors.append({"user_id": str(club.get("user_id")), "username": club.get("username", ""), "error": str(exc)})
            print(f"Skipping {club.get('username')}: {exc}", file=sys.stderr)
            continue
        (active if record["status"] == "active" else inactive).append(record)

    result = {
        "generated_at": now.isoformat(),
        "checked_count": len(active) + len(inactive),
        "active_count": len(active),
        "inactive_count": len(inactive),
        "error_count": len(errors),
        "active": active,
        "inactive": inactive,
        "errors": errors,
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
