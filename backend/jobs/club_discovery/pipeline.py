import os
from datetime import datetime, timezone
from typing import Any

from app.college_config import get_college_config
from app.services.hiker_client import HikerAPIError, HikerClient
from jobs.club_discovery.accounts import extract_public_accounts
from jobs.club_discovery.outputs import write_outputs


def run(
    college_key: str | None = None,
    seed_account: str | None = None,
    output_dir: str | None = None,
    college_name: str | None = None,
) -> dict[str, Any]:
    """Run one scheduler-safe college club discovery refresh."""
    if college_name is None:
        config = get_college_config(college_key)
        target_account = seed_account or config["seed_account"]
        resolved_college_key = config["college_key"]
        resolved_college_name = config["college_name"]
    else:
        if not college_key or not seed_account:
            raise ValueError("college_key and seed_account are required with college_name.")
        target_account = seed_account
        resolved_college_key = college_key
        resolved_college_name = college_name

    client = HikerClient()

    profile = client.resolve_user(target_account)
    user_pk = profile.get("pk") or profile.get("id")
    if not user_pk:
        raise HikerAPIError(f"Could not resolve seed account: {target_account}")

    raw_accounts, refresh_stats = client.get_following(user_pk)
    public_accounts = extract_public_accounts(raw_accounts)

    result = {
        "college_key": resolved_college_key,
        "college_name": resolved_college_name,
        "seed_account": target_account,
        "seed_user_id": str(user_pk),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "following": public_accounts,
        "clubs": [],
        "refresh_stats": {
            **refresh_stats,
            "public_accounts": len(public_accounts),
            "private_accounts_skipped": len(raw_accounts) - len(public_accounts),
            "ai_classification": "pending",
        },
    }

    if output_dir:
        result["files"] = write_outputs(result, output_dir=output_dir)
    return result


def default_output_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
