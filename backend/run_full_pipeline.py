"""One-click runner: discovery job + AI filter job, chained.

Runs the two existing jobs back to back so a single command produces a final
clubs.json of AI-approved Instagram club accounts:

1. jobs.club_discovery.run()   -> resolves the seed account, walks its
   following graph, writes following.json / following.csv / clubs.json
   (empty placeholder) into --output-dir.
2. jobs.ai.club_filter.run_filter() -> reads that following.json and
   overwrites clubs.json with the AI-approved club accounts (full original
   records). No other files are created.

Neither job is modified; this only chains the two entrypoints that already
exist (discover_clubs.py and run_ai_club_filter.py).
"""

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from app.college_config import get_college_config
from jobs.ai.club_filter import DEFAULT_BATCH_SIZE, run_filter
from jobs.club_discovery import run as run_discovery

ROOT = Path(__file__).resolve().parent
DEFAULT_SAMPLE_DIR = ROOT / "sample"
DEFAULT_PROMPT = ROOT / "jobs" / "ai" / "prompts" / "club_filter.md"


def run_full_pipeline(
    college_key: str | None = None,
    seed_account: str | None = None,
    output_dir: Path = DEFAULT_SAMPLE_DIR,
    prompt_path: Path = DEFAULT_PROMPT,
    allow_empty: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    discovery_result = run_discovery(
        college_key=college_key,
        seed_account=seed_account,
        output_dir=str(output_dir),
    )

    filter_result = run_filter(
        input_path=output_dir / "following.json",
        filtered_output_path=output_dir / "clubs.json",
        prompt_path=prompt_path,
        allow_empty=allow_empty,
        batch_size=batch_size,
    )

    return {
        "college": discovery_result["college_name"],
        "seed_account": discovery_result["seed_account"],
        "following_count": filter_result["original_count"],
        "club_count": filter_result["filtered_count"],
        "skipped_count": filter_result["skipped_count"],
        "output_dir": str(output_dir),
        "clubs_file": filter_result["filtered_output"],
    }


def main() -> int:
    load_dotenv(ROOT.parent / ".env")
    parser = argparse.ArgumentParser(
        description="Discover a college's Instagram following graph and filter it down to clubs with DeepSeek."
    )
    parser.add_argument("--college", default=os.getenv("COLLEGE_KEY", "hunter"))
    parser.add_argument("--seed-account", default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_SAMPLE_DIR)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--allow-empty", action="store_true")
    args = parser.parse_args()

    config = get_college_config(args.college)
    seed = args.seed_account or config["seed_account"]

    summary = run_full_pipeline(
        college_key=args.college,
        seed_account=seed,
        output_dir=args.output_dir,
        prompt_path=args.prompt,
        allow_empty=args.allow_empty,
        batch_size=args.batch_size,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

