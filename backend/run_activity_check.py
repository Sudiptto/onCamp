import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from jobs.activity_check import run

ROOT = Path(__file__).resolve().parent
DEFAULT_SAMPLE_DIR = ROOT / "sample"
DEFAULT_TEST_LIMIT = 5


def main() -> int:
    load_dotenv(ROOT.parent / ".env")
    parser = argparse.ArgumentParser(description="Split clubs.json into active/inactive clubs by last post date.")
    parser.add_argument("--clubs", type=Path, default=DEFAULT_SAMPLE_DIR / "clubs.json")
    parser.add_argument("--output", type=Path, default=DEFAULT_SAMPLE_DIR / "club_activity.json")
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_TEST_LIMIT,
        help=f"Only check the first N clubs (default {DEFAULT_TEST_LIMIT}) to keep HikerAPI cost low.",
    )
    parser.add_argument("--all", action="store_true", help="Check every club in clubs.json (one API call each).")
    args = parser.parse_args()

    result = run(args.clubs, args.output, limit=None if args.all else args.limit)
    print(json.dumps({k: v for k, v in result.items() if k not in ("active", "inactive")}, indent=2))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
