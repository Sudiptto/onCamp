import csv
import json
import os
from typing import Any


def _save_json(accounts: list[dict[str, Any]], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file_handle:
        json.dump(accounts, file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")


def _save_csv(accounts: list[dict[str, Any]], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    base_fields = [
        "username",
        "user_id",
        "full_name",
        "profile_pic_url",
        "is_private",
    ]
    optional_fields = ["account_type", "club_match_terms", "activity_status"]
    fieldnames = base_fields + [
        field for field in optional_fields
        if any(field in account for account in accounts)
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
        writer.writeheader()
        for account in accounts:
            row = {field: account.get(field, "") for field in fieldnames}
            if "club_match_terms" in row:
                row["club_match_terms"] = ",".join(account.get("club_match_terms", []))
            writer.writerow(row)


def write_outputs(data: dict[str, Any], output_dir: str) -> dict[str, str]:
    output_root = os.path.abspath(output_dir)
    paths = {
        "following_json": os.path.join(output_root, "following.json"),
        "following_csv": os.path.join(output_root, "following.csv"),
        "json": os.path.join(output_root, "clubs.json"),
        "csv": os.path.join(output_root, "clubs.csv"),
    }
    following = data.get("following") or []
    clubs = data.get("clubs") or []
    _save_json(following, paths["following_json"])
    _save_csv(following, paths["following_csv"])
    _save_json(clubs, paths["json"])
    _save_csv(clubs, paths["csv"])
    return paths
