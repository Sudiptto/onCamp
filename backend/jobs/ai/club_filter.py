import json
import os
import sys
from pathlib import Path
from typing import Any

from openai import BadRequestError, OpenAI


REQUIRED_FIELDS = ("username", "user_id", "full_name")
DEFAULT_BATCH_SIZE = 40


def load_prompt(prompt_path: Path) -> str:
    return prompt_path.read_text(encoding="utf-8")


def build_candidates(accounts: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {field: str(account.get(field) or "") for field in REQUIRED_FIELDS}
        for account in accounts
    ]


def _parse_response(content: str) -> list[dict[str, Any]]:
    parsed = json.loads(content)
    if not isinstance(parsed, dict) or not isinstance(parsed.get("clubs"), list):
        raise ValueError("DeepSeek response must be an object with a clubs array")

    clubs = []
    for item in parsed["clubs"]:
        if not isinstance(item, dict) or not item.get("user_id"):
            raise ValueError("Every AI club result must include user_id")
        clubs.append(item)
    return clubs


def classify_with_deepseek(
    candidates: list[dict[str, str]],
    prompt_path: Path,
) -> list[dict[str, Any]]:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("Missing DEEPSEEK_API_KEY in the local .env file")

    client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    prompt = load_prompt(prompt_path)
    response = client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(candidates, ensure_ascii=False)},
        ],
    )
    content = response.choices[0].message.content or ""
    return _parse_response(content)


def _classify_batch_safely(
    candidates: list[dict[str, str]],
    prompt_path: Path,
    skipped: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Classify a batch; bisect and drop the single account DeepSeek's content filter rejects."""
    if not candidates:
        return []
    try:
        return classify_with_deepseek(candidates, prompt_path)
    except BadRequestError as exc:
        if "content exists risk" not in str(exc).lower():
            raise
        if len(candidates) == 1:
            offender = candidates[0]
            skipped.append({"user_id": offender["user_id"], "username": offender["username"]})
            print(
                f"Skipping {offender['username']} ({offender['user_id']}): "
                "rejected by DeepSeek's content filter",
                file=sys.stderr,
            )
            return []
        midpoint = len(candidates) // 2
        left = _classify_batch_safely(candidates[:midpoint], prompt_path, skipped)
        right = _classify_batch_safely(candidates[midpoint:], prompt_path, skipped)
        return left + right


def classify_all(
    candidates: list[dict[str, str]],
    prompt_path: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    skipped: list[dict[str, str]] = []
    ai_clubs: list[dict[str, Any]] = []
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start : start + batch_size]
        ai_clubs.extend(_classify_batch_safely(batch, prompt_path, skipped))
    return ai_clubs, skipped


def filter_original_accounts(
    original_accounts: list[dict[str, Any]],
    ai_clubs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    original_by_id = {
        str(account.get("user_id")): account
        for account in original_accounts
        if account.get("user_id")
    }
    selected_ids = {str(club["user_id"]) for club in ai_clubs}
    unknown_ids = selected_ids - original_by_id.keys()
    if unknown_ids:
        raise ValueError("DeepSeek returned user IDs that were not in the original following file")
    return [account for account in original_accounts if str(account.get("user_id")) in selected_ids]


def run_filter(
    input_path: Path,
    filtered_output_path: Path,
    prompt_path: Path,
    allow_empty: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    original_accounts = json.loads(input_path.read_text(encoding="utf-8-sig"))
    if not isinstance(original_accounts, list):
        raise ValueError("The original following file must contain a JSON array")

    candidates = build_candidates(original_accounts)
    ai_clubs, skipped = classify_all(candidates, prompt_path, batch_size=batch_size)
    if not ai_clubs and not allow_empty:
        raise ValueError("DeepSeek returned zero clubs; refusing to overwrite clubs.json")

    filtered_accounts = filter_original_accounts(original_accounts, ai_clubs)
    filtered_output_path.write_text(
        json.dumps(filtered_accounts, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "original_count": len(original_accounts),
        "ai_club_count": len(ai_clubs),
        "filtered_count": len(filtered_accounts),
        "skipped_count": len(skipped),
        "skipped": skipped,
        "filtered_output": str(filtered_output_path),
    }
