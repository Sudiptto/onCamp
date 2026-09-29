import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from jobs.ai.club_filter import DEFAULT_BATCH_SIZE, run_filter


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_PROMPT = ROOT / "jobs" / "ai" / "prompts" / "club_filter.md"


def main() -> int:
    load_dotenv(ROOT.parent / ".env")
    parser = argparse.ArgumentParser(
        description="Classify following.json with DeepSeek and write clubs.json."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_DATA_DIR / "following.json",
        help="Original following JSON; it is never modified.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_DATA_DIR / "clubs.json",
        help="Where to write the AI-approved club accounts.",
    )
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Accounts sent to DeepSeek per request; smaller batches isolate content-filter rejections faster.",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Allow an empty AI result to overwrite clubs.json.",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    result = run_filter(
        input_path=args.input,
        filtered_output_path=args.output,
        prompt_path=args.prompt,
        allow_empty=args.allow_empty,
        batch_size=args.batch_size,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

