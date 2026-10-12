import hashlib
import json
import os
import sys
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    BadRequestError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)


REQUIRED_FIELDS = ("username", "user_id", "full_name")
DEFAULT_BATCH_SIZE = 40
DEFAULT_CACHE_NAME = "club_classifications.json"

# DeepSeek's API works with the openai package, we just point base_url at it.
# The package waits 10 minutes by default, so set a shorter limit (seconds of silence).
REQUEST_TIMEOUT_SECONDS = 60
MAX_TRANSIENT_RETRIES = 2
MAX_MALFORMED_RETRIES = 1
RETRY_BASE_DELAY_SECONDS = 2.0
MAX_RETRY_DELAY_SECONDS = 30.0

# Retry these. APIConnectionError also covers timeouts.
TRANSIENT_ERRORS = (APIConnectionError, RateLimitError, InternalServerError)

# Anything else it refuses fails the same way every time. Codes are from DeepSeek's error docs.
REJECTION_HINTS = {
    400: "if this mentions the model, check DEEPSEEK_MODEL",
    401: "check DEEPSEEK_API_KEY",
    402: "the DeepSeek account is out of balance",
    404: "if this mentions the model, check DEEPSEEK_MODEL",
    422: "if this mentions the model, check DEEPSEEK_MODEL",
}

# DeepSeek announced these names would be discontinued on 2026-07-24.
LEGACY_MODELS = {"deepseek-chat", "deepseek-reasoner"}


class MalformedResponseError(ValueError):
    """DeepSeek replied, but not with the JSON we asked for."""


class IncompleteClassification(RuntimeError):
    """Some accounts could not be classified. Progress is saved, run again to finish."""

    def __init__(self, missing_count: int, failed: list[dict[str, Any]]) -> None:
        super().__init__(
            f"{missing_count} accounts could not be classified. "
            "Progress was saved, run again to finish the rest."
        )
        self.missing_count = missing_count
        self.failed = failed


def get_model() -> str:
    return os.getenv("DEEPSEEK_MODEL", "deepseek-flash")


def get_prompt_version(prompt: str) -> str:
    """Short fingerprint of the prompt text, so editing the prompt makes old results outdated."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]


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
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=0,  # retries happen in _classify_with_retries so they get logged
    )
    prompt = load_prompt(prompt_path)
    model = get_model()
    options = {}
    if model not in LEGACY_MODELS:
        # Newer models think before answering by default, which is slower and ignores
        # temperature. deepseek-chat was always the non-thinking mode, so ask for that.
        options["extra_body"] = {"thinking": {"type": "disabled"}}
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(candidates, ensure_ascii=False)},
        ],
        **options,
    )
    content = response.choices[0].message.content or ""
    try:
        return _parse_response(content)
    except ValueError as exc:  # bad JSON is a ValueError too
        raise MalformedResponseError(str(exc)) from exc


def _retry_delay(error: Exception, failures: int) -> float:
    """Wait as long as Retry-After says if it is there, otherwise 2s, 4s, 8s."""
    headers = getattr(getattr(error, "response", None), "headers", None) or {}
    try:
        return min(float(headers["retry-after"]), MAX_RETRY_DELAY_SECONDS)
    except (KeyError, ValueError):
        return min(RETRY_BASE_DELAY_SECONDS * 2 ** (failures - 1), MAX_RETRY_DELAY_SECONDS)


def _classify_with_retries(
    candidates: list[dict[str, str]],
    prompt_path: Path,
) -> list[dict[str, Any]]:
    transient_failures = 0
    malformed_failures = 0
    while True:
        try:
            clubs = classify_with_deepseek(candidates, prompt_path)
            batch_ids = {item["user_id"] for item in candidates}
            if any(str(club["user_id"]) not in batch_ids for club in clubs):
                # Named an account we didn't send. Treat it as a bad reply so it never gets saved.
                raise MalformedResponseError("it named an account that was not in the batch")
            return clubs
        except MalformedResponseError as exc:
            malformed_failures += 1
            if malformed_failures > MAX_MALFORMED_RETRIES:
                raise
            print(f"DeepSeek sent a malformed response ({exc}), trying this batch again", file=sys.stderr)
        except TRANSIENT_ERRORS as exc:
            transient_failures += 1
            if transient_failures > MAX_TRANSIENT_RETRIES:
                raise
            delay = _retry_delay(exc, transient_failures)
            print(f"DeepSeek error ({type(exc).__name__}), retrying in {delay:g}s", file=sys.stderr)
            time.sleep(delay)


def _classify_batch_safely(
    candidates: list[dict[str, str]],
    prompt_path: Path,
    skipped: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Classify a batch; bisect and drop the single account DeepSeek's content filter rejects."""
    if not candidates:
        return []
    try:
        return _classify_with_retries(candidates, prompt_path)
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


def _describe_rejection(exc: APIStatusError) -> str:
    hint = REJECTION_HINTS.get(exc.status_code)
    prefix = f"DeepSeek rejected the request ({exc.status_code})"
    if hint:
        prefix += f", {hint}"
    return f"{prefix}: {str(exc.message)[:150]}"


def _record_failure(failed: list[dict[str, Any]], batch: list[dict[str, str]], reason: str) -> None:
    user_ids = [item["user_id"] for item in batch]
    failed.append({"user_ids": user_ids, "reason": reason})
    print(f"Could not classify {len(user_ids)} accounts ({reason})", file=sys.stderr)


def classify_all(
    candidates: list[dict[str, str]],
    prompt_path: Path,
    batch_size: int = DEFAULT_BATCH_SIZE,
    on_batch_done: Callable[[list[dict[str, str]], list[dict[str, Any]], list[dict[str, str]]], None] | None = None,
    failed: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    skipped: list[dict[str, str]] = []
    ai_clubs: list[dict[str, Any]] = []
    if failed is None:
        failed = []

    for start in range(0, len(candidates), batch_size):
        batch = candidates[start : start + batch_size]
        skipped_before = len(skipped)
        try:
            batch_clubs = _classify_batch_safely(batch, prompt_path, skipped)
        except MalformedResponseError as exc:
            # Only this batch is bad, so log it and carry on with the others.
            del skipped[skipped_before:]
            _record_failure(failed, batch, f"malformed response: {exc}")
            continue
        except TRANSIENT_ERRORS as exc:
            # Retries ran out, probably an outage or rate limit. Stop instead of failing every batch.
            del skipped[skipped_before:]
            _record_failure(failed, batch, f"{type(exc).__name__} after retries")
            break
        except APIStatusError as exc:
            # Bad key, no balance, or a retired model fails every batch the same way. Stop and say why.
            del skipped[skipped_before:]
            _record_failure(failed, batch, _describe_rejection(exc))
            break

        ai_clubs.extend(batch_clubs)
        if on_batch_done is not None:
            on_batch_done(batch, batch_clubs, skipped[skipped_before:])
    return ai_clubs, skipped


def load_cache(cache_path: Path | None) -> dict[str, dict[str, Any]]:
    if cache_path is None or not cache_path.exists():
        return {}
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # A broken cache only costs some extra API calls, so start fresh instead of crashing.
        print(f"Ignoring unreadable cache file {cache_path}", file=sys.stderr)
        return {}
    return cache if isinstance(cache, dict) else {}


def save_cache(cache_path: Path, cache: dict[str, dict[str, Any]]) -> None:
    # Write a temp file and swap it in, so a crash halfway through can't corrupt the cache.
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_name(cache_path.name + ".tmp")
    temp_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(cache_path)


def _is_current(entry: Any, model: str, prompt_version: str) -> bool:
    return (
        isinstance(entry, dict)
        and entry.get("model") == model
        and entry.get("prompt_version") == prompt_version
    )


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
    cache_path: Path | None = None,
) -> dict[str, Any]:
    original_accounts = json.loads(input_path.read_text(encoding="utf-8-sig"))
    if not isinstance(original_accounts, list):
        raise ValueError("The original following file must contain a JSON array")

    candidates = build_candidates(original_accounts)
    model = get_model()
    prompt_version = get_prompt_version(load_prompt(prompt_path))
    if model in LEGACY_MODELS:
        print(
            f"Warning: DeepSeek announced {model} would be discontinued on 2026-07-24. "
            "If requests fail, set DEEPSEEK_MODEL to a current model such as deepseek-flash "
            "(see api-docs.deepseek.com/updates).",
            file=sys.stderr,
        )

    # Only results from this model and this prompt count, anything older gets redone.
    classifications = {
        user_id: entry
        for user_id, entry in load_cache(cache_path).items()
        if _is_current(entry, model, prompt_version)
    }
    to_classify = [item for item in candidates if item["user_id"] not in classifications]

    def remember(batch, batch_clubs, batch_skipped) -> None:
        # Called after every finished batch, so a later failure keeps this progress.
        club_ids = {str(club["user_id"]) for club in batch_clubs}
        rejected_ids = {item["user_id"] for item in batch_skipped}
        classified_at = datetime.now(timezone.utc).isoformat()
        for item in batch:
            user_id = item["user_id"]
            if not user_id:
                continue
            classifications[user_id] = {
                "is_club": user_id in club_ids,
                "rejected": user_id in rejected_ids,
                "model": model,
                "prompt_version": prompt_version,
                "classified_at": classified_at,
            }
        if cache_path is not None:
            save_cache(cache_path, classifications)

    failed: list[dict[str, Any]] = []
    new_clubs, skipped = classify_all(
        to_classify, prompt_path, batch_size=batch_size, on_batch_done=remember, failed=failed
    )

    missing = [
        item for item in to_classify
        if item["user_id"] and item["user_id"] not in classifications
    ]
    if missing:
        # Don't write a clubs.json that's missing accounts. Finished batches are saved, so a rerun only does the rest.
        raise IncompleteClassification(len(missing), failed)

    current_ids = {item["user_id"] for item in candidates}
    fresh_ids = {item["user_id"] for item in to_classify}
    cached_club_ids = [
        user_id
        for user_id, entry in classifications.items()
        if entry["is_club"] and user_id in current_ids and user_id not in fresh_ids
    ]
    ai_clubs = new_clubs + [{"user_id": user_id} for user_id in cached_club_ids]
    if not ai_clubs and not allow_empty:
        raise ValueError(
            "DeepSeek returned zero clubs; refusing to overwrite clubs.json. "
            "If that looks wrong, run again with --no-cache."
        )

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
        "classified_count": len(to_classify),
        "cached_count": len(candidates) - len(to_classify),
        "filtered_output": str(filtered_output_path),
    }
