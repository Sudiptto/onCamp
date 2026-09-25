import argparse
import json
import os
import sys

from app.college_config import get_college_config
from app.services.club_discovery import write_discovery_outputs
from app.services.hiker_client import HikerAPIError
from jobs.club_discovery import run
from jobs.club_discovery.pipeline import default_output_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover club accounts from a seed Instagram account.")
    parser.add_argument("--college", default=os.getenv("COLLEGE_KEY", "hunter"), help="College key for the current campus; currently Hunter is the only supported value")
    parser.add_argument("--seed-account", default=None, help="Instagram username to resolve and scan")
    parser.add_argument("--output-dir", default=default_output_dir(), help="Directory to write discovery outputs")
    args = parser.parse_args()

    config = get_college_config(args.college)
    seed = args.seed_account or config["seed_account"]

    try:
        result = run(college_key=args.college, seed_account=seed, output_dir=args.output_dir)
    except HikerAPIError as exc:
        print(f"Discovery failed: {exc}", file=sys.stderr)
        result = {
            "college_key": config["college_key"],
            "college_name": config["college_name"],
            "seed_account": seed,
            "seed_user_id": None,
            "generated_at": None,
            "following": [],
            "clubs": [],
            "refresh_stats": {"pages_fetched": 0, "raw_accounts": 0},
            "error": str(exc),
        }

    file_map = result.get("files") or write_discovery_outputs(result, output_dir=args.output_dir)
    print(json.dumps({
        "college": config["college_name"],
        "seed_account": seed,
        "following_count": len(result.get("following") or result.get("clubs") or []),
        "refresh_stats": result.get("refresh_stats", {}),
        "files": file_map,
        "error": result.get("error"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
