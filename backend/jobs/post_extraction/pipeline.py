import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.hiker_client import HikerClient
from jobs.post_extraction.posts import DEFAULT_POST_COUNT, extract_recent_posts

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "posts"


def extract_club_posts(
    club: dict[str, Any],
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    count: int = DEFAULT_POST_COUNT,
    client: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Fetch a club's recent posts via HikerAPI and write them to <output_dir>/<username>.json.

    The file holds both the parsed posts and the raw API response so the data can be inspected.
    """
    client = client or HikerClient()
    now = now or datetime.now(timezone.utc)
    raw = client.get_user_medias(club["user_id"])
    posts = extract_recent_posts(raw, count)
    result = {
        "user_id": str(club["user_id"]),
        "username": club.get("username", ""),
        "fetched_at": now.isoformat(),
        "post_count": len(posts),
        "posts": posts,
        "raw_response": raw,
    }

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    name = result["username"] or result["user_id"]
    (output_dir / f"{name}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return result


def find_club(clubs_path: Path, username: str) -> dict[str, Any]:
    clubs = json.loads(Path(clubs_path).read_text(encoding="utf-8-sig"))
    for club in clubs:
        if club.get("username", "").lower() == username.lower():
            return club
    raise ValueError(f"Club '{username}' not found in {clubs_path}")


def main(argv: list[str] | None = None) -> int:
    import argparse

    data_dir = Path(__file__).resolve().parents[2] / "data"
    parser = argparse.ArgumentParser(description="Extract recent posts for one club.")
    parser.add_argument("--username", default="hunter_bsa")
    parser.add_argument("--count", type=int, default=DEFAULT_POST_COUNT)
    parser.add_argument("--clubs", type=Path, default=data_dir / "clubs.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    club = find_club(args.clubs, args.username)
    result = extract_club_posts(club, args.output_dir, args.count)
    print(f"Saved {result['post_count']} posts for {result['username']} to {args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
