import os
from datetime import datetime, timezone
from typing import Any

from app.college_config import get_college_config
from app.services.hiker_client import HikerAPIError, HikerClient
from jobs.club_discovery.accounts import extract_public_accounts
from jobs.club_discovery.activity import add_activity_status, split_activity_status
from jobs.club_discovery.classification import classify_clubs
from jobs.club_discovery.outputs import write_outputs


def run(
    college_key: str | None = None,
    seed_account: str | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Run one scheduler-safe college club discovery refresh."""
    config = get_college_config(college_key)
    target_account = seed_account or config["seed_account"]
    client = HikerClient()

    profile = client.resolve_user(target_account)
    user_pk = profile.get("pk") or profile.get("id")
    if not user_pk:
        raise HikerAPIError(f"Could not resolve seed account: {target_account}")

    raw_accounts, refresh_stats = client.get_following(user_pk)
    public_accounts = extract_public_accounts(raw_accounts)
    clubs, other_accounts = classify_clubs(public_accounts, config.get("keywords"))
    clubs = add_activity_status(clubs)
    activity_groups = split_activity_status(clubs)

    result = {
        "college_key": config["college_key"],
        "college_name": config["college_name"],
        "seed_account": target_account,
        "seed_user_id": str(user_pk),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "following": public_accounts,
        "clubs": clubs,
        "other_accounts": other_accounts,
        "active_clubs": activity_groups["active"],
        "inactive_clubs": activity_groups["inactive"],
        "unknown_activity_clubs": activity_groups["unknown"],
        "refresh_stats": {
            **refresh_stats,
            "public_accounts": len(public_accounts),
            "private_accounts_skipped": len(raw_accounts) - len(public_accounts),
            "club_candidates": len(clubs),
            "other_accounts": len(other_accounts),
            "active_clubs": len(activity_groups["active"]),
            "inactive_clubs": len(activity_groups["inactive"]),
            "unknown_activity_clubs": len(activity_groups["unknown"]),
        },
    }

    if output_dir:
        result["files"] = write_outputs(result, output_dir=output_dir)
    return result


def default_output_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
