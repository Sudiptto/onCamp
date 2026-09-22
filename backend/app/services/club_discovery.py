import csv
import json
import os
from datetime import datetime, timezone
from typing import Any

from app.college_config import get_college_config
from app.services.hiker_client import HikerAPIError, HikerClient


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def normalize_account(account: dict[str, Any]) -> dict[str, Any]:
    user_id = account.get("pk") or account.get("id") or account.get("user_id")
    username = _normalize_text(account.get("username"))
    full_name = _normalize_text(account.get("full_name") or account.get("name"))
    profile_pic_url = _normalize_text(account.get("profile_pic_url") or account.get("profile_picture") or "")

    return {
        "username": username,
        "user_id": str(user_id),
        "full_name": full_name,
        "profile_pic_url": profile_pic_url,
        "is_private": bool(account.get("is_private") or False),
    }


def extract_following(accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a clean pool of public accounts from the seed account's following list.

    This is intentionally broad: we are not filtering for clubs yet. The goal is to
    create a candidate pool that can be passed to a later AI or rule-based classifier.
    This phase may run every few months to refresh the raw graph without doing heavy
    downstream filtering in real time.
    """
    extracted: list[dict[str, Any]] = []
    for account in accounts:
        normalized = normalize_account(account)
        if normalized["is_private"]:
            continue
        extracted.append(normalized)
    return extracted


def save_clubs_json(clubs: list[dict[str, Any]], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file_handle:
        json.dump(clubs, file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")


def save_clubs_csv(clubs: list[dict[str, Any]], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fieldnames = [
        "username",
        "user_id",
        "full_name",
        "profile_pic_url",
        "is_private",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
        writer.writeheader()
        for club in clubs:
            writer.writerow({
                "username": club.get("username", ""),
                "user_id": club.get("user_id", ""),
                "full_name": club.get("full_name", ""),
                "profile_pic_url": club.get("profile_pic_url", ""),
                "is_private": club.get("is_private", False),
            })


def discover_clubs(college_key: str | None = None, seed_account: str | None = None) -> dict[str, Any]:
    # CRON: run this refresh job every few months to rebuild the raw follow graph
    # and then feed the candidate list into a later classification pass.
    config = get_college_config(college_key)
    target_account = seed_account or config["seed_account"]
    client = HikerClient()

    profile = client.resolve_user(target_account)
    user_pk = profile.get("pk") or profile.get("id")
    if not user_pk:
        raise HikerAPIError(f"Could not resolve seed account: {target_account}")

    accounts, refresh_stats = client.get_following(user_pk)
    following = extract_following(accounts)
    refresh_stats["public_accounts"] = len(following)
    refresh_stats["private_accounts_skipped"] = len(accounts) - len(following)

    return {
        "college_key": config["college_key"],
        "college_name": config["college_name"],
        "seed_account": target_account,
        "seed_user_id": str(user_pk),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "following": following,
        "clubs": following,
        "refresh_stats": refresh_stats,
    }


def write_discovery_outputs(data: dict[str, Any], output_dir: str = "data") -> dict[str, str]:
    output_root = os.path.abspath(output_dir)
    following_json = os.path.join(output_root, "following.json")
    following_csv = os.path.join(output_root, "following.csv")
    clubs_json = os.path.join(output_root, "clubs.json")
    clubs_csv = os.path.join(output_root, "clubs.csv")

    pool = data.get("following") or data.get("clubs") or []
    save_clubs_json(pool, following_json)
    save_clubs_csv(pool, following_csv)

    # Keep the club names as compatibility aliases during the early raw-capture phase.
    save_clubs_json(pool, clubs_json)
    save_clubs_csv(pool, clubs_csv)

    return {
        "following_json": following_json,
        "following_csv": following_csv,
        "json": clubs_json,
        "csv": clubs_csv,
    }
